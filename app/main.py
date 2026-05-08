from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uuid

app = FastAPI()

# ===== Fake DB =====
users = {}
tokens = {}
exams = {}

# ===== Models =====
class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class GenerateExamRequest(BaseModel):
    subject: str
    num_questions: int

class SubmitExamRequest(BaseModel):
    exam_id: str
    answers: list[str]

# ===== Auth =====
def get_current_user(token: str):
    if token not in tokens:
        raise HTTPException(status_code=401, detail="Invalid token")
    return tokens[token]

# ===== API =====

# 1. Register
@app.post("/register")
def register(data: RegisterRequest):
    if data.username in users:
        raise HTTPException(status_code=400, detail="User exists")
    users[data.username] = data.password
    return {"message": "Register success"}

# 2. Login
@app.post("/login")
def login(data: LoginRequest):
    if users.get(data.username) != data.password:
        raise HTTPException(status_code=401, detail="Wrong credentials")
    
    token = str(uuid.uuid4())
    tokens[token] = data.username
    return {"token": token}

# 3. Generate exam (FAKE AI)
@app.post("/generate-exam")
def generate_exam(data: GenerateExamRequest, token: str):
    user = get_current_user(token)

    exam_id = str(uuid.uuid4())

    questions = []
    for i in range(data.num_questions):
        questions.append({
            "question": f"Câu {i+1}: {data.subject} là gì?",
            "options": ["A", "B", "C", "D"],
            "answer": "A"
        })

    exams[exam_id] = {
        "user": user,
        "questions": questions
    }

    return {
        "exam_id": exam_id,
        "questions": questions
    }

# 4. Submit exam
@app.post("/submit-exam")
def submit_exam(data: SubmitExamRequest, token: str):
    user = get_current_user(token)

    exam = exams.get(data.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    score = 0
    for i, q in enumerate(exam["questions"]):
        if i < len(data.answers) and data.answers[i] == q["answer"]:
            score += 1

    return {
        "user": user,
        "score": score,
        "total": len(exam["questions"])
    }