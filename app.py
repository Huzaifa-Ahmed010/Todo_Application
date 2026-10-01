from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import SessionLocal, engine, Base
from models import User, Task
from passlib.context import CryptContext

Base.metadata.create_all(bind=engine)

app = FastAPI()
templates = Jinja2Templates(directory="Templates")
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")


def normalize_password(password: str) -> str:
    if password is None:
        return ""
    return password.encode("utf-8")[:72].decode("utf-8", errors="ignore")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    return templates.TemplateResponse(request, "register.html", {})


@app.post("/register")
async def register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.username == username).first():
        return templates.TemplateResponse(
            request,
            "register.html",
            {"error": "Username already exists"},
        )

    safe_password = normalize_password(password)
    hashed_password = pwd_context.hash(safe_password)
    user = User(username=username, hashed_password=hashed_password)
    db.add(user)
    db.commit()
    return RedirectResponse(url="/login", status_code=303)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse(request, "login.html", {})


@app.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.username == username).first()
    if not user:
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "User not found"},
        )

    safe_password = normalize_password(password)
    if not pwd_context.verify(safe_password, user.hashed_password):
        return templates.TemplateResponse(
            request,
            "login.html",
            {"error": "Incorrect password"},
        )

    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(key="user_id", value=str(user.id), httponly=True)
    return response


@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("user_id")
    return response


@app.get("/", response_class=HTMLResponse)
async def read_index(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    user = None
    tasks = []

    if user_id:
        user = db.query(User).filter(User.id == int(user_id)).first()
        if user:
            tasks = db.query(Task).filter(Task.owner_id == int(user_id)).all()

    return templates.TemplateResponse(
        request,
        "Index.html",
        {"tasks": tasks, "user": user},
    )


@app.post("/tasks")
async def add_task(
    request: Request,
    title: str = Form(...),
    description: str | None = Form(default=None),
    deadline: str | None = Form(default=None),
    category: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    task = Task(
        title=title,
        description=description,
        deadline=deadline,
        category=category,
        owner_id=int(user_id),
    )
    db.add(task)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/tasks/{task_id}/toggle")
async def toggle_tasks(task_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == int(user_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    task.completed = not task.completed
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/tasks/{task_id}/delete")
async def delete_task(task_id: int, request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == int(user_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    db.delete(task)
    db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/tasks/{task_id}/update")
@app.put("/tasks/{task_id}/update")
async def update_task(
    task_id: int,
    request: Request,
    title: str | None = Form(default=None),
    db: Session = Depends(get_db),
):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    task = db.query(Task).filter(Task.id == task_id, Task.owner_id == int(user_id)).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if title is not None and title.strip():
        task.title = title.strip()
        db.commit()

    return RedirectResponse(url="/", status_code=303)


@app.get("/add_task", response_class=HTMLResponse)
async def add_task_page(request: Request, db: Session = Depends(get_db)):
    user_id = request.cookies.get("user_id")
    if not user_id:
        return RedirectResponse(url="/login", status_code=303)

    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user:
        return RedirectResponse(url="/login", status_code=303)

    return templates.TemplateResponse(request, "add_task.html", {"user": user})
