import time
from worker.tasks import process_document
from celery.result import AsyncResult

def run_test():
    file_path = "/Users/nbgdeveloper/thaidq/thaidq_agent/uploads/e2f360f222ae4596ba25297a3eed86b4.pdf"
    print(f"Submitting task for {file_path}")
    task = process_document.delay(file_path)
    print(f"Task ID: {task.id}")
    
    while not task.ready():
        print(f"Task state: {task.state}")
        time.sleep(2)
        
    print(f"Final state: {task.state}")
    if task.failed():
        print(f"Error: {task.result}")
        print(f"Traceback: {task.traceback}")
    else:
        print(f"Result: {task.result}")

if __name__ == "__main__":
    run_test()
