from typing import Optional, List, Literal, Dict, Any
from pydantic import BaseModel

VALID_SAMPLER_TYPES = Literal[
    "bernoulli", "bernoulli_mixture", "binomial", "category", "datetime",
    "gaussian", "person", "person_from_faker", "poisson", "scipy",
    "subcategory", "timedelta", "uniform", "uuid",
]

class SamplerColumn(BaseModel):
    name: str
    sampler_type: VALID_SAMPLER_TYPES
    params: Optional[Dict[str, Any]] = None
    convert_to: Optional[str] = None

class ExpressionColumn(BaseModel):
    name: str
    expr: str
    convert_to: Optional[str] = None

class LLMTextColumn(BaseModel):
    name: str
    prompt: str
    system_prompt: Optional[str] = None

class LLMCodeColumn(BaseModel):
    name: str
    prompt: str
    code_lang: str
    system_prompt: Optional[str] = None

class LLMStructuredColumn(BaseModel):
    name: str
    prompt: str
    output_format: Dict[str, Any]
    system_prompt: Optional[str] = None

class ScoreOption(BaseModel):
    name: str
    description: str
    options: Dict[str, str]

class LLMJudgeColumn(BaseModel):
    name: str
    prompt: str
    scores: List[ScoreOption]
    system_prompt: Optional[str] = None

class ValidationColumn(BaseModel):
    name: str
    target_columns: List[str]
    validator_type: str
    validator_params: Dict[str, Any]

class GenerateRequest(BaseModel):
    model_provider: Literal[
        "openai", "nvidiabuild", "anthropic", "deepseek", "groq", 
        "google", "microsoft", "mistral", "custom"
    ]
    model_id: str
    provider_api_key: str
    provider_base_url: Optional[str] = None
    provider_api_version: Optional[str] = None
    
    num_records: Optional[int] = 50
    temperature: Optional[float] = 0.5
    top_p: Optional[float] = 1.0
    max_tokens: Optional[int] = 1024
    
    sampler_columns: Optional[List[SamplerColumn]] = None
    expression_columns: Optional[List[ExpressionColumn]] = None
    llm_text_columns: Optional[List[LLMTextColumn]] = None
    llm_code_columns: Optional[List[LLMCodeColumn]] = None
    llm_structured_columns: Optional[List[LLMStructuredColumn]] = None
    llm_judge_columns: Optional[List[LLMJudgeColumn]] = None
    validation_columns: Optional[List[ValidationColumn]] = None
