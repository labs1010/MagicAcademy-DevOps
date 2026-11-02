from pydantic import BaseModel, ConfigDict, Field


class Registration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-z0-9_]+$")
    password: str = Field(min_length=10, max_length=128)


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=80)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    display_name: str
    role: str


class CourseIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=120)
    capacity: int = Field(ge=1, le=100000)


class CourseOut(CourseIn):
    id: int
    available_seats: int


class EnrollmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    course_id: int
