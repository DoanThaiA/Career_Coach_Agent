from typing import List, Optional, Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from langchain_core.prompts import ChatPromptTemplate

from src.core.logger import get_logger
from src.utils import get_extraction_llm, generate_with_retry_and_correction, get_schema_instruction

logger = get_logger(__name__)

Proficiency = Literal["beginner", "intermediate", "advanced", "expert"]
LanguageProficiency = Literal["native", "fluent", "professional", "intermediate", "basic"]
EmploymentType = Literal["full-time", "part-time", "contract", "internship", "freelance"]
SkillCategory = Literal["language", "framework", "tool", "platform", "database", "other"]
SkillWeight = Literal["must_have", "important", "nice_to_have"]
DegreeLevel = Literal["high_school", "associate", "bachelor", "master", "phd", "none"]
SeniorityLevel = Literal["intern", "junior", "mid", "senior", "lead", "manager", "director"]
RemoteOption = Literal["onsite", "remote", "hybrid"]


class Location(BaseModel):
    city: str = Field(description="Thành phố")
    country: Optional[str] = Field(default=None, description="Quốc gia")
    remote_option: Optional[RemoteOption] = Field(default=None, description="Tùy chọn làm việc")


class JobInfo(BaseModel):
    job_title: str = Field(description="Tên vị trí tuyển dụng")
    department: Optional[str] = Field(default=None, description="Phòng ban")
    company_name: Optional[str] = Field(default=None, description="Tên công ty")
    location: Optional[Location] = Field(default=None, description="Địa điểm làm việc")
    employment_type: Optional[str] = Field(default=None, description="Hình thức làm việc (full-time, part-time, contract, internship, freelance)")
    seniority_level: Optional[str] = Field(default=None, description="Cấp bậc: intern/junior/mid/senior/lead/manager/director")

    @field_validator("seniority_level", mode="before")
    @classmethod
    def normalize_seniority(cls, v):
        if not v:
            return None
        mapping = {
            "engineer": "mid", "developer": "mid", "software engineer": "mid",
            "senior engineer": "senior", "senior developer": "senior",
            "lead engineer": "lead", "tech lead": "lead",
            "staff engineer": "senior", "principal": "senior",
        }
        v_lower = str(v).lower().strip()
        return mapping.get(v_lower, v_lower)

    @field_validator("employment_type", mode="before")
    @classmethod
    def normalize_employment(cls, v):
        if not v:
            return None
        mapping = {
            "fulltime": "full-time", "full time": "full-time",
            "parttime": "part-time", "part time": "part-time",
            "freelancer": "freelance",
        }
        v_lower = str(v).lower().strip()
        return mapping.get(v_lower, v_lower)


class Summary(BaseModel):
    role_summary: str = Field(description="Tóm tắt mô tả công việc 2-3 câu")


class ExperienceRequirements(BaseModel):
    min_years_experience_total: Optional[float] = Field(default=None, description="Tổng số năm kinh nghiệm tối thiểu")
    min_years_experience_relevant: Optional[float] = Field(
        default=None, description="Số năm kinh nghiệm liên quan trực tiếp tối thiểu"
    )
    required_industry_background: List[str] = Field(description="Lĩnh vực/ngành nghề yêu cầu (vd: fintech, e-commerce)"
    )
    management_experience_required: bool = Field(description="Yêu cầu kinh nghiệm quản lý?")


class EducationRequirements(BaseModel):
    min_degree_level: Optional[DegreeLevel] = Field(default=None, description="Bằng cấp tối thiểu")
    preferred_majors: List[str] = Field(description="Các chuyên ngành ưu tiên")
    required: bool = Field(description="Bằng cấp có bắt buộc hay chỉ ưu tiên")

class RequiredSkill(BaseModel):
    name: str = Field(description="Tên kỹ năng/công nghệ")
    category: SkillCategory = Field(description="Phân loại kỹ năng")
    min_proficiency: Optional[Proficiency] = Field(default=None, description="Mức độ thành thạo tối thiểu yêu cầu")
    min_years: Optional[float] = Field(default=None, description="Số năm kinh nghiệm tối thiểu cho kỹ năng này")
    weight: SkillWeight = Field(
        default="important",
        description="must_have = bắt buộc (loại nếu thiếu) | important = rất quan trọng | nice_to_have = điểm cộng",
    )

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class SkillsRequirement(BaseModel):
    required_technical_skills: List[RequiredSkill] = Field(description="Kỹ năng kỹ thuật bắt buộc/quan trọng (weight = must_have | important)"
    )
    preferred_technical_skills: List[RequiredSkill] = Field(description="Kỹ năng kỹ thuật ưu tiên, không bắt buộc (weight luôn = nice_to_have)"
    )
    required_soft_skills: List[str] = Field(description="Kỹ năng mềm bắt buộc")

    @model_validator(mode="after")
    def dedup_and_normalize(self) -> "SkillsRequirement":
        for skill in self.preferred_technical_skills:
            skill.weight = "nice_to_have"

        def _dedup(skills: List[RequiredSkill]) -> List[RequiredSkill]:
            seen: dict[tuple[str, str], RequiredSkill] = {}
            for s in skills:
                key = (s.name.lower(), s.category)
                if key not in seen:
                    seen[key] = s
            return list(seen.values())

        self.required_technical_skills = _dedup(self.required_technical_skills)
        self.preferred_technical_skills = _dedup(self.preferred_technical_skills)
        return self

    def all_skills(self) -> List[RequiredSkill]:
        """Gộp required + preferred thành 1 list duy nhất, tiện cho việc loop khi scoring."""
        return [*self.required_technical_skills, *self.preferred_technical_skills]

    def must_have_names(self) -> set[str]:
        return {s.name.lower() for s in self.required_technical_skills if s.weight == "must_have"}


class CertificationRequired(BaseModel):
    name: str = Field(description="Tên chứng chỉ")
    required: bool = Field(default=False, description="Bắt buộc phải có hay không")


class LanguageRequired(BaseModel):
    language: str = Field(description="Ngôn ngữ yêu cầu")
    min_proficiency: Optional[LanguageProficiency] = Field(default=None, description="Mức độ tối thiểu")
    required: bool = Field(default=False, description="Bắt buộc phải có hay không")


class Qualifications(BaseModel):
    must_have: List[str] = Field(description="Điều kiện bắt buộc khác (thiếu sẽ bị loại)")
    nice_to_have: List[str] = Field(description="Điều kiện ưu tiên (điểm cộng)")


class SalaryRange(BaseModel):
    min: Optional[float] = Field(default=None, description="Mức lương tối thiểu")
    max: Optional[float] = Field(default=None, description="Mức lương tối đa")
    currency: str = Field(description="Đơn vị tiền tệ (VD: USD, VND)")


class Compensation(BaseModel):
    salary_range: Optional[SalaryRange] = Field(default=None, description="Khoảng lương")
    benefits: List[str] = Field(description="Danh sách phúc lợi, đãi ngộ")


class JDRequirements(BaseModel):
    job_info: JobInfo = Field(description="Thông tin chung về công việc")
    summary: Optional[Summary] = Field(default=None, description="Tóm tắt công việc")
    experience_requirements: Optional[ExperienceRequirements] = Field(default=None, description="Yêu cầu kinh nghiệm")
    education_requirements: Optional[EducationRequirements] = Field(default=None, description="Yêu cầu bằng cấp")
    skills: SkillsRequirement = Field(description="Yêu cầu kỹ năng")
    certifications_required: List[CertificationRequired] = Field(description="Yêu cầu chứng chỉ")
    languages_required: List[LanguageRequired] = Field(description="Yêu cầu ngoại ngữ")
    responsibilities: List[str] = Field(description="Trách nhiệm, công việc chính")
    qualifications: Optional[Qualifications] = Field(default=None, description="Điều kiện cần/đủ khác")
    compensation: Optional[Compensation] = Field(default=None, description="Thông tin lương thưởng, phúc lợi")

    @property
    def job_title(self) -> str:
        return self.job_info.job_title

    @property
    def level(self) -> Optional[str]:
        return self.job_info.seniority_level

    @property
    def min_years_experience(self) -> Optional[float]:
        return self.experience_requirements.min_years_experience_total if self.experience_requirements else None

    def all_required_skill_names(self) -> set[str]:
        """Set lowercase mọi skill (required + preferred) - so trực tiếp với
        CVInformation.all_technologies() ở bước matching."""
        if not self.skills:
            return set()
        return {s.name.lower() for s in self.skills.all_skills()}

    def must_have_skill_names(self) -> set[str]:
        """Chỉ các skill weight=must_have - dùng làm hard filter, loại CV ngay
        nếu thiếu bất kỳ skill nào trong set này."""
        return self.skills.must_have_names() if self.skills else set()


PARSE_JD_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Chuyên gia Phân tích Yêu cầu Tuyển dụng (Expert Job Description Analyst).
Nhiệm vụ: đọc toàn bộ văn bản Job Description (JD) và bóc tách dữ liệu chuẩn xác thành JSON theo schema.

HƯỚNG DẪN BẮT BUỘC:

1. ĐẦY ĐỦ, KHÔNG BỎ SÓT:
   Rà soát kỹ để không bỏ sót MỘT KỸ NĂNG, CÔNG NGHỆ, PHÚC LỢI, CHỨNG CHỈ nào.

2. SKILLS - DẠNG PHẲNG (flat list), KHÔNG group theo category:
   - `required_technical_skills`: mọi skill bắt buộc/quan trọng, mỗi item gồm
     name, category (language|framework|tool|platform|database|other),
     min_proficiency, min_years, weight.
   - `weight` phân biệt rõ:
     + "must_have": bắt buộc phải có, JD ghi "Yêu cầu", "Bắt buộc", "Required".
     + "important": rất quan trọng nhưng chưa hẳn là điều kiện loại ngay.
     + "nice_to_have": chỉ nên dùng cho required_technical_skills nếu JD dùng
       từ "ưu tiên nhẹ" nhưng vẫn liệt kê chung mục yêu cầu.
   - `preferred_technical_skills`: các skill JD ghi rõ là "ưu tiên", "preferred",
     "is a plus", KHÔNG thuộc mục yêu cầu bắt buộc. weight của các skill này
     luôn là nice_to_have.

3. KINH NGHIỆM: phân biệt `min_years_experience_total` (tổng năm đi làm) và
   `min_years_experience_relevant` (năm kinh nghiệm ở vị trí/mảng tương đương).

4. NGUYÊN TẮC SỰ THẬT: chỉ trích xuất thông tin có thật trong JD, không bịa.
   Trường không có thông tin thì để `null` hoặc mảng rỗng `[]`.

═══════════════════════════════════════════
NỘI DUNG JD CẦN BÓC TÁCH:
═══════════════════════════════════════════
{jd_context}

═══════════════════════════════════════════
VÍ DỤ MẪU (FLAT SKILL LIST)
═══════════════════════════════════════════
[Input JD trích đoạn]:
Yêu cầu: Thành thạo Python (tối thiểu 3 năm), có kinh nghiệm FastAPI.
Ưu tiên: biết Docker, AWS.

[Output JSON mong đợi]:
{{
  "skills": {{
    "required_technical_skills": [
      {{ "name": "Python", "category": "language", "min_proficiency": "advanced", "min_years": 3.0, "weight": "must_have" }},
      {{ "name": "FastAPI", "category": "framework", "min_proficiency": null, "min_years": null, "weight": "important" }}
    ],
    "preferred_technical_skills": [
      {{ "name": "Docker", "category": "tool", "min_proficiency": null, "min_years": null, "weight": "nice_to_have" }},
      {{ "name": "AWS", "category": "platform", "min_proficiency": null, "min_years": null, "weight": "nice_to_have" }}
    ],
    "required_soft_skills": []
  }}
}}
""")


from langchain_core.runnables.config import RunnableConfig

async def parse_jd(jd_context: str, config: Optional[RunnableConfig] = None) -> JDRequirements | dict:
    logger.info("▶ Bắt đầu xử lý extractor_node (parse_jd) ...")

    if not jd_context or not jd_context.strip():
        logger.warning("✖ Nội dung JD rỗng hoặc không tồn tại")
        return {"errors": ["Nội dung JD rỗng hoặc không tồn tại"]}

    try:
        llm = get_extraction_llm()
        prompt_text = PARSE_JD_PROMPT.format(jd_context=jd_context)
        fallback_prompt = prompt_text + get_schema_instruction(JDRequirements)
        jd_parsed = await generate_with_retry_and_correction(
            llm, fallback_prompt, JDRequirements, max_retries=3, config=config
        )

        if not jd_parsed.skills or not jd_parsed.skills.all_skills():
            logger.warning("⚠ JD được parse nhưng không có thông tin kỹ năng")

        logger.info(
            "✔ Xử lý extractor_node (parse_jd) thành công | "
            f"title={jd_parsed.job_title} | must_have={len(jd_parsed.must_have_skill_names())} | "
            f"total_skills={len(jd_parsed.all_required_skill_names())}"
        )
        return jd_parsed

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node (parse_jd): {e}", exc_info=True)
        return {"errors": [f"Lỗi bóc tách JD: {str(e)}"]}