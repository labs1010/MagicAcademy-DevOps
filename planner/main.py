from fastapi import FastAPI, Query

app = FastAPI(title="MagicAcademy Group Planner")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/groups")
def groups(students: int = Query(ge=0), group_size: int = Query(gt=0)):
    return {"groups": (students + group_size - 1) // group_size}
