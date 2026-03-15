from pydantic import BaseModel, HttpUrl, Field
from typing import Optional, List, Dict, Any


class JiraConfig(BaseModel):
    host: HttpUrl
    user_email: str
    api_token: str
    project_key: str
    issue_type: str = 'Task'


class EmailConfig(BaseModel):
    recipients: List[str]
    subject: Optional[str] = 'Test Report'
    body: Optional[str] = None


class RunOptions(BaseModel):
    generate_tests: bool = True
    simulate_executor: bool = True
    test_max_steps: int = 20
    planner_model: str = 'gpt-3.5-turbo'
    jira: Optional[JiraConfig] = None
    email: Optional[EmailConfig] = None
    extra: Optional[Dict[str, Any]] = Field(default_factory=dict)


class JobCreateResponse(BaseModel):
    job_id: str
    status: str


class JobStatus(BaseModel):
    job_id: str
    status: str
    logs: Optional[List[str]] = []
    artifact_url: Optional[str] = None

