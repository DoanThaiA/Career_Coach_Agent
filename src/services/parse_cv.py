import re
from datetime import date
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



def _parse_year_month(value: Optional[str]) -> Optional[tuple[int, int]]:
    if not value:
        return None
    value = value.strip().lower()
    if value in ("present", "hiện tại", "now", "current", "nay", "đến nay"):
        today = date.today()
        return today.year, today.month

    # Thử YYYY-MM hoặc YYYY/MM
    match = re.search(r"\b(\d{4})[-/](\d{1,2})\b", value)
    if match:
        return int(match.group(1)), int(match.group(2))
        
    # Thử MM/YYYY hoặc MM-YYYY
    match = re.search(r"\b(\d{1,2})[-/](\d{4})\b", value)
    if match:
        return int(match.group(2)), int(match.group(1))
        
    # Thử chỉ có YYYY
    match = re.search(r"\b(\d{4})\b", value)
    if match:
        return int(match.group(1)), 1
        
    return None


def _months_between(start: Optional[str], end: Optional[str]) -> Optional[int]:
    start_ym = _parse_year_month(start)
    end_ym = _parse_year_month(end)
    if not start_ym or not end_ym:
        return None
    months = (end_ym[0] - start_ym[0]) * 12 + (end_ym[1] - start_ym[1])
    return max(months, 0)


class Location(BaseModel):
    city: str = Field(description="Thành phố")
    country: Optional[str] = Field(default=None, description="Quốc gia")


class CandidateInfo(BaseModel):
    full_name: str = Field(description="Họ và tên ứng viên")
    email: str = Field(description="Email liên hệ")
    phone: Optional[str] = Field(default=None, description="Số điện thoại")
    location: Optional[Location] = Field(default=None, description="Địa điểm sinh sống/làm việc")
    linkedin_url: Optional[str] = Field(default=None, description="Đường dẫn LinkedIn (URL)")
    portfolio_url: Optional[str] = Field(default=None, description="Đường dẫn Portfolio/GitHub/Website (URL)")

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: Optional[str]) -> Optional[str]:
        return v.strip().lower() if v else v


class Summary(BaseModel):
    professional_title: Optional[str] = Field(default=None, description="Chức danh chuyên môn chính")
    career_summary: str = Field(description="Tóm tắt ngắn gọn (2-3 câu)")


class WorkExperience(BaseModel):
    company: str = Field(description="Tên công ty")
    job_title: str = Field(description="Chức danh công việc")
    start_date: Optional[str] = Field(default=None, description="YYYY-MM hoặc YYYY")
    end_date: Optional[str] = Field(default=None, description="YYYY-MM, YYYY hoặc 'present'")
    location: Optional[str] = Field(default=None, description="Địa điểm làm việc")
    employment_type: Optional[EmploymentType] = Field(default=None, description="Hình thức làm việc")
    responsibilities: List[str] = Field(description="Nhiệm vụ, công việc chính")
    achievements: List[str] = Field(description="Thành tựu có số liệu cụ thể")
    technologies_used: List[str] = Field(description="Công nghệ/công cụ/framework đã dùng")


class Education(BaseModel):
    institution: str = Field(description="Trường/Cơ sở đào tạo")
    degree: str = Field(description="Bằng cấp")
    major: Optional[str] = Field(default=None, description="Chuyên ngành")
    start_date: Optional[str] = Field(default=None, description="Năm bắt đầu (YYYY)")
    end_date: Optional[str] = Field(default=None, description="Năm kết thúc (YYYY)")
    gpa: Optional[str] = Field(default=None, description="GPA nếu có")


class TechnicalSkill(BaseModel):
    name: str = Field(description="Tên kỹ năng/công nghệ")
    category: SkillCategory = Field(description="Phân loại kỹ năng")
    proficiency: Optional[Proficiency] = Field(default=None, description="Mức độ thành thạo")

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class Skills(BaseModel):
    technical_skills: List[TechnicalSkill] = Field(description="Danh sách kỹ năng kỹ thuật (dạng phẳng, mỗi item có category riêng)"
    )
    soft_skills: List[str] = Field(description="Danh sách kỹ năng mềm")

    @model_validator(mode="after")
    def dedup_skills(self) -> "Skills":
        # Loại bỏ trùng lặp theo (name lowercase, category) - giữ bản ghi có nhiều
        # thông tin hơn (có proficiency) nếu bị trùng.
        seen: dict[tuple[str, str], TechnicalSkill] = {}
        for skill in self.technical_skills:
            key = (skill.name.lower(), skill.category)
            if key not in seen:
                seen[key] = skill
            else:
                existing = seen[key]
                if skill.proficiency and not existing.proficiency:
                    existing.proficiency = skill.proficiency
        self.technical_skills = list(seen.values())
        return self

    def skill_names(self) -> List[str]:
        """Trả về list tên skill (lowercase) - dùng để so khớp nhanh với JD."""
        return [s.name.lower() for s in self.technical_skills]


class Certification(BaseModel):
    name: str = Field(description="Tên chứng chỉ")
    issuer: Optional[str] = Field(default=None, description="Tổ chức cấp")
    issue_date: Optional[str] = Field(default=None, description="Ngày cấp (YYYY-MM hoặc YYYY)")
    expiry_date: Optional[str] = Field(default=None, description="Ngày hết hạn")


class Language(BaseModel):
    language: str = Field(description="Tên ngôn ngữ")
    proficiency: Optional[LanguageProficiency] = Field(default=None, description="Mức độ sử dụng")


class Project(BaseModel):
    name: str = Field(description="Tên dự án")
    description: Optional[str] = Field(default=None, description="Mô tả dự án")
    technologies: List[str] = Field(description="Công nghệ sử dụng")
    role: Optional[str] = Field(default=None, description="Vai trò đảm nhiệm")
    url: Optional[str] = Field(default=None, description="Link demo/GitHub")


class CVInformation(BaseModel):
    candidate_info: CandidateInfo = Field(description="Thông tin cá nhân")
    summary: Optional[Summary] = Field(default=None, description="Tóm tắt")
    work_experience: List[WorkExperience] = Field(description="Kinh nghiệm làm việc")
    education: List[Education] = Field(description="Học vấn")
    skills: Optional[Skills] = Field(default=None, description="Kỹ năng chuyên môn & kỹ năng mềm")
    certifications: List[Certification] = Field(description="Chứng chỉ")
    languages: List[Language] = Field(description="Ngoại ngữ")
    projects: List[Project] = Field(description="Dự án cá nhân/thực tế")
    
    # Internal field to hold calculated YOE without prompting LLM for it
    calculated_total_yoe: Optional[float] = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def recompute_total_experience(self) -> "CVInformation":
        # Tính tổng số năm kinh nghiệm bằng cách gộp (merge) các khoảng thời gian làm việc
        # để tránh tính trùng lặp (double counting) khi ứng viên làm nhiều công việc cùng lúc.
        intervals = []
        for w in self.work_experience:
            start_ym = _parse_year_month(w.start_date)
            end_ym = _parse_year_month(w.end_date)
            if start_ym and end_ym:
                start_months = start_ym[0] * 12 + start_ym[1]
                end_months = end_ym[0] * 12 + end_ym[1]
                if start_months <= end_months:
                    intervals.append((start_months, end_months))
        
        total_months = 0
        if intervals:
            # Sắp xếp theo ngày bắt đầu
            intervals.sort(key=lambda x: x[0])
            merged = [intervals[0]]
            for current in intervals[1:]:
                prev = merged[-1]
                if current[0] <= prev[1]:
                    # Có trùng lặp thời gian -> gộp lại
                    merged[-1] = (prev[0], max(prev[1], current[1]))
                else:
                    merged.append(current)
            
            for m in merged:
                total_months += (m[1] - m[0])
                
        # Fallback nếu không parse được qua khoảng thời gian, lấy tổng duration theo từng tháng độc lập
        if total_months == 0:
            for w in self.work_experience:
                dur = _months_between(w.start_date, w.end_date)
                if dur:
                    total_months += dur

        if total_months > 0:
            self.calculated_total_yoe = round(total_months / 12, 1)
        return self

    # ---- convenience accessors, hữu ích cho bước matching với JD ----
    @property
    def full_name(self) -> Optional[str]:
        return self.candidate_info.full_name if self.candidate_info else None

    @property
    def email(self) -> Optional[str]:
        return self.candidate_info.email if self.candidate_info else None

    @property
    def phone(self) -> Optional[str]:
        return self.candidate_info.phone if self.candidate_info else None

    @property
    def total_yoe(self) -> Optional[float]:
        return self.calculated_total_yoe

    def all_technologies(self) -> set[str]:
        """Gộp mọi công nghệ xuất hiện trong CV (skills + work_experience + projects)
        thành 1 set lowercase duy nhất - dùng trực tiếp để so sánh với
        JD.required_technical_skills mà không cần lặp qua nhiều nơi."""
        techs: set[str] = set()
        if self.skills:
            techs.update(self.skill_lower(s.name) for s in self.skills.technical_skills)
        for job in self.work_experience:
            techs.update(self.skill_lower(t) for t in job.technologies_used)
        for proj in self.projects:
            techs.update(self.skill_lower(t) for t in proj.technologies)
        return techs

    @staticmethod
    def skill_lower(name: str) -> str:
        return name.strip().lower()


EXTRACT_PROMPT = ChatPromptTemplate.from_template("""
Bạn là một Hệ thống Trích xuất Dữ liệu CV Chuyên nghiệp (Expert HR Data Parser).
Nhiệm vụ: phân tích văn bản CV thô và bóc tách dữ liệu chuẩn xác thành các trường thông tin theo đúng yêu cầu cấu trúc (structured format).

HƯỚNG DẪN BẮT BUỘC:

1. ĐẦY ĐỦ & KHÔNG BỊA ĐẶT:
- Trích xuất MỌI công nghệ, công cụ, ngôn ngữ, thành tích, chứng chỉ xuất hiện trong CV, không bỏ sót.
- CHỈ trích xuất thông tin thực sự có trong CV. Nếu không có thông tin, bỏ qua hoặc để null/rỗng.

2. THÔNG TIN CƠ BẢN:
- Bắt buộc cần có: full_name, email, phone.
- Và nếu có: location, linkedin_url, portfolio_url, professional_title, career_summary.

3. KINH NGHIỆM LÀM VIỆC (work_experience):
- Định dạng ngày ưu tiên: `YYYY-MM`. Đang làm thì dùng `"present"`.
- KHÔNG cần tự tính `duration_months`.
- Tách bạch rõ: `responsibilities` (nhiệm vụ hàng ngày), `achievements` (kết quả có số liệu) và `technologies_used` (công nghệ dùng tại công ty đó).

4. KỸ NĂNG (skills.technical_skills) - DẠNG PHẲNG (flat list), MỖI PHẦN TỬ CÓ:
   name, category (language|framework|tool|platform|database|other), proficiency.
   Không gộp nhóm theo category, hệ thống sẽ tự xử lý dedup.
   `soft_skills`: danh sách kỹ năng mềm.
   `languages`: ngoại ngữ và mức độ.

5. KHÁC: Trích xuất đầy đủ education, certifications, projects.

═══════════════════════════════════════════
NỘI DUNG VĂN BẢN CV CẦN BÓC TÁCH:
═══════════════════════════════════════════
{cv_context}
""")


from langchain_core.runnables.config import RunnableConfig

async def parse_cv(cv_content: str, config: Optional[RunnableConfig] = None) -> CVInformation | dict:
    """Node bóc tách CV: text thô → CVInformation (structured)."""
    logger.info("▶ Bắt đầu xử lý extractor_node (parse_cv) ...")

    if not cv_content or not cv_content.strip():
        logger.warning("✖ Nội dung CV rỗng hoặc không tồn tại")
        return {"errors": ["Nội dung CV rỗng hoặc không tồn tại"]}

    try:
        llm = get_extraction_llm()
        prompt_text = EXTRACT_PROMPT.format(cv_context=cv_content)
        fallback_prompt = prompt_text + get_schema_instruction(CVInformation)
        cv_parsed = await generate_with_retry_and_correction(
            llm, fallback_prompt, CVInformation, max_retries=3, config=config
        )

        if not cv_parsed.work_experience and not cv_parsed.skills and not cv_parsed.education:
            logger.warning("⚠ CV được parse nhưng không có dữ liệu quan trọng (work_experience/skills/education đều rỗng)")

        logger.info(
            "✔ Xử lý extractor_node (parse_cv) thành công | "
            f"YOE={cv_parsed.total_yoe} | skills={len(cv_parsed.skills.technical_skills) if cv_parsed.skills else 0} | "
            f"jobs={len(cv_parsed.work_experience)}"
        )
        return cv_parsed

    except Exception as e:
        logger.error(f"✖ Lỗi khi xử lý extractor_node (parse_cv): {e}", exc_info=True)
        raise