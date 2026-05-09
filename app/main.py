from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
import uuid

app = FastAPI()

# ===== Fake DB =====
users = {}
tokens = {}
exams = {}
folders = {}  # folder_id -> folder data
folder_id_counter = {"val": 1}

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

class FolderCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None

class FolderMove(BaseModel):
    target_parent_id: Optional[int] = None

# ===== Auth =====
def get_current_user(token: str):
    if token not in tokens:
        raise HTTPException(status_code=401, detail="Invalid token")
    return tokens[token]

# ===== Folder Helpers =====
def get_parent_path(parent_id: Optional[int]) -> str:
    if parent_id is None:
        return "/root"
    parent = folders.get(parent_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent folder not found")
    return parent["path"]

def is_descendant(folder_id: int, target_id: int) -> bool:
    """Kiểm tra target_id có phải con cháu của folder_id không."""
    visited = set()
    current_id = target_id
    while current_id is not None:
        if current_id in visited:
            break
        if current_id == folder_id:
            return True
        visited.add(current_id)
        current = folders.get(current_id)
        if not current:
            break
        current_id = current.get("parent_id")
    return False

def update_paths_recursive(folder_id: int, old_prefix: str, new_prefix: str):
    """Cập nhật path của folder và toàn bộ con cháu."""
    folder = folders.get(folder_id)
    if not folder:
        return
    folder["path"] = new_prefix + folder["path"][len(old_prefix):]
    for fid, f in folders.items():
        if f.get("parent_id") == folder_id:
            update_paths_recursive(fid, old_prefix, new_prefix)

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

# 3. Generate exam
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
    exams[exam_id] = {"user": user, "questions": questions}
    return {"exam_id": exam_id, "questions": questions}

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
    return {"user": user, "score": score, "total": len(exam["questions"])}

# 5. Tạo thư mục
@app.post("/folders")
def create_folder(data: FolderCreate, token: str):
    user = get_current_user(token)

    # Kiểm tra trùng tên trong cùng cha
    for f in folders.values():
        if f["parent_id"] == data.parent_id and f["name"] == data.name:
            raise HTTPException(status_code=409, detail="Folder name already exists in this location")

    parent_path = get_parent_path(data.parent_id)
    path = f"{parent_path}/{data.name}"

    fid = folder_id_counter["val"]
    folder_id_counter["val"] += 1

    folders[fid] = {
        "id": fid,
        "name": data.name,
        "parent_id": data.parent_id,
        "path": path,
        "owner": user
    }
    return {"message": "Folder created", "data": folders[fid]}

# 6. Danh sách thư mục gốc
@app.get("/folders")
def list_folders(token: str):
    user = get_current_user(token)
    result = [f for f in folders.values() if f["parent_id"] is None and f["owner"] == user]
    return {"data": result}

# 7. Xem nội dung thư mục
@app.get("/folders/{folder_id}")
def get_folder(folder_id: int, token: str):
    get_current_user(token)
    folder = folders.get(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    children = [f for f in folders.values() if f["parent_id"] == folder_id]
    return {"folder": folder, "children": children}

# 8. ⭐ Di chuyển thư mục
@app.patch("/folders/{folder_id}/move")
def move_folder(folder_id: int, data: FolderMove, token: str):
    user = get_current_user(token)

    # Folder tồn tại?
    folder = folders.get(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")

    # Quyền sở hữu?
    if folder["owner"] != user:
        raise HTTPException(status_code=403, detail="Permission denied")

    # Di chuyển vào chính nó?
    if data.target_parent_id == folder_id:
        raise HTTPException(status_code=400, detail="Cannot move folder into itself")

    # Không thay đổi gì?
    if folder["parent_id"] == data.target_parent_id:
        return {"message": "Folder already at this location", "data": folder}

    # Di chuyển vào con cháu?
    if data.target_parent_id is not None:
        if not folders.get(data.target_parent_id):
            raise HTTPException(status_code=404, detail="Target folder not found")
        if is_descendant(folder_id, data.target_parent_id):
            raise HTTPException(status_code=400, detail="Cannot move folder into its own subfolder")

    # Trùng tên ở đích?
    for f in folders.values():
        if f["parent_id"] == data.target_parent_id and f["name"] == folder["name"] and f["id"] != folder_id:
            raise HTTPException(status_code=409, detail=f"Folder '{folder['name']}' already exists at target location")

    # Cập nhật path cascade
    old_path = folder["path"]
    parent_path = get_parent_path(data.target_parent_id)
    new_path = f"{parent_path}/{folder['name']}"

    update_paths_recursive(folder_id, old_path, new_path)
    folder["parent_id"] = data.target_parent_id

    return {"message": "Folder moved successfully", "data": folder}

# 9. Xóa thư mục
@app.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, token: str):
    user = get_current_user(token)
    folder = folders.get(folder_id)
    if not folder:
        raise HTTPException(status_code=404, detail="Folder not found")
    if folder["owner"] != user:
        raise HTTPException(status_code=403, detail="Permission denied")
    
    # Xóa cascade tất cả con cháu
    to_delete = []
    def collect(fid):
        to_delete.append(fid)
        for f in folders.values():
            if f["parent_id"] == fid:
                collect(f["id"])
    collect(folder_id)
    for fid in to_delete:
        folders.pop(fid, None)

    return {"message": "Folder deleted"}