# AutoDocumentation Engine - Low Level Design (LLD)
## Simplified Direct Generation Model

**Project**: AI-Powered Code-to-Documentation Platform  
**Version**: 2.0 (Simplified)  
**Date**: May 2026  
**Audience**: Backend Engineers, DevOps, QA Engineers

---

## Table of Contents
1. [API Specifications](#api-specifications)
2. [Data Models](#data-models)
3. [Agent Implementation Details](#agent-implementation-details)
4. [Tool Specifications](#tool-specifications)
5. [LangGraph Workflow](#langgraph-workflow)
6. [RAG Implementation](#rag-implementation)
7. [Repository Manager](#repository-manager)
8. [Error Handling & Retry Logic](#error-handling--retry-logic)
9. [Testing Strategy](#testing-strategy)
10. [Code Structure & Patterns](#code-structure--patterns)

---

## API Specifications

### Endpoint 1: Generate Documentation

**Endpoint**: `POST /api/v1/generate`

**Request**:
```json
{
  "repo_url": "https://github.com/user/my-repo.git",
  "formats": ["markdown", "html", "pdf"],
  "include_openapi": true
}
```

**Validation**:
```python
- Valid GitHub URL format
- HTTPS protocol only
- Repository must be accessible
- Formats must be from allowed list
```

**Response** (202 Accepted - Async Processing):
```json
{
  "job_id": "doc_7a3f9e2c",
  "status": "queued",
  "estimated_completion_seconds": 180,
  "message": "Documentation generation queued successfully"
}
```

**Response Codes**:
```
202 - Accepted (Job queued)
400 - Bad Request (Invalid URL or formats)
429 - Too Many Requests (Rate limit exceeded)
500 - Server Error
```

---

### Endpoint 2: Check Job Status

**Endpoint**: `GET /api/v1/status/{job_id}`

**Query Parameters**: None

**Response** (While Processing):
```json
{
  "job_id": "doc_7a3f9e2c",
  "status": "in_progress",
  "progress": 45,
  "current_stage": "api_documentation",
  "elapsed_seconds": 45,
  "estimated_remaining_seconds": 135
}
```

**Status Values**:
```
queued           - Waiting in queue
in_progress      - Currently processing
completed        - Ready for download
failed           - Generation failed
expired          - Exceeded 24h TTL
```

**Response** (When Completed):
```json
{
  "job_id": "doc_7a3f9e2c",
  "status": "completed",
  "progress": 100,
  "completed_at": "2024-05-01T14:28:30Z",
  "generation_time_seconds": 158,
  "available_formats": ["markdown", "html", "pdf"],
  "download_url": "/api/v1/download/doc_7a3f9e2c"
}
```

**Response** (When Failed):
```json
{
  "job_id": "doc_7a3f9e2c",
  "status": "failed",
  "error": {
    "code": "REPO_NOT_FOUND",
    "message": "Repository not accessible",
    "details": "Authentication required or repository does not exist",
    "timestamp": "2024-05-01T14:15:00Z"
  }
}
```

---

### Endpoint 3: Download Documentation

**Endpoint**: `GET /api/v1/download/{job_id}`

**Query Parameters**:
```
?format=markdown  // Optional: return specific format
                  // If not specified, returns ZIP with all formats
```

**Response** (Single Format):
```
Content-Type: text/markdown
Content-Disposition: attachment; filename="documentation.md"

# Project Name

Documentation content...
```

**Response** (All Formats - ZIP):
```
Content-Type: application/zip
Content-Disposition: attachment; filename="documentation.zip"

Structure:
├── README.md
├── API_REFERENCE.md
├── ARCHITECTURE.md
├── documentation.html
├── documentation.pdf
├── openapi.json
└── swagger.yaml
```

**Response Codes**:
```
200 - OK (Returning file)
202 - Accepted (Still processing, try again later)
404 - Not Found (Job ID doesn't exist)
410 - Gone (Job expired after 24 hours)
```

---

### Endpoint 4: Health Check (Optional)

**Endpoint**: `GET /api/v1/health`

**Response**:
```json
{
  "status": "healthy",
  "version": "2.0",
  "timestamp": "2024-05-01T14:28:30Z",
  "services": {
    "api": "healthy",
    "redis": "healthy",
    "worker": "healthy"
  }
}
```

---

## Data Models

### Pydantic Models for Request/Response

```python
from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional
from enum import Enum

class DocumentFormat(str, Enum):
    """Supported output formats"""
    MARKDOWN = "markdown"
    HTML = "html"
    PDF = "pdf"
    OPENAPI = "openapi"

class GenerateDocRequest(BaseModel):
    """API request to generate documentation"""
    repo_url: HttpUrl = Field(..., description="GitHub repository URL")
    formats: List[DocumentFormat] = Field(
        default=["markdown", "html"],
        description="Output formats"
    )
    include_openapi: bool = Field(
        default=True,
        description="Include OpenAPI specification"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "repo_url": "https://github.com/user/project.git",
                "formats": ["markdown", "html", "pdf"],
                "include_openapi": True
            }
        }

class JobStatus(str, Enum):
    """Job status enumeration"""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    EXPIRED = "expired"

class StatusResponse(BaseModel):
    """Response for status check"""
    job_id: str
    status: JobStatus
    progress: int = Field(ge=0, le=100)
    current_stage: Optional[str] = None
    elapsed_seconds: int = 0
    estimated_remaining_seconds: Optional[int] = None
    error: Optional[dict] = None

class DownloadResponse(BaseModel):
    """Response for download endpoint"""
    job_id: str
    available_formats: List[DocumentFormat]
    download_url: str
    expires_at: str  # ISO format timestamp
```

### Redis Data Models

```python
# Job tracking (auto-expire after 24 hours)
job:{job_id}:metadata
{
    "repo_url": "https://github.com/user/repo.git",
    "formats": ["markdown", "html"],
    "status": "in_progress",
    "created_at": "2024-05-01T12:00:00Z",
    "started_at": "2024-05-01T12:00:05Z",
    "expires_at": "2024-05-02T12:00:00Z"
}

job:{job_id}:progress
{
    "progress_percent": 45,
    "current_stage": "api_documentation",
    "agent_outputs": {
        "code_analyzer": "completed",
        "architecture_detective": "completed",
        "api_documenter": "in_progress",
        "examples_generator": "queued",
        "consistency_validator": "queued"
    }
}

job:{job_id}:outputs
{
    "markdown": "# Project\n...",
    "html": "<html>...</html>",
    "pdf": "base64_encoded_pdf",
    "openapi": "{\"openapi\": \"3.0.0\", ...}"
}

# TTL Index: All keys expire after 86400 seconds (24 hours)
```

---

## Agent Implementation Details

### Base Agent Class

```python
from abc import ABC, abstractmethod
from typing import Dict, Any
from datetime import datetime

class BaseAgent(ABC):
    """Base class for all documentation agents"""
    
    def __init__(self, llm, name: str):
        self.llm = llm
        self.name = name
        self.logger = logging.getLogger(f"agent.{name}")
    
    @abstractmethod
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Execute agent logic"""
        pass
    
    def log_execution(self, stage: str):
        """Log agent execution"""
        self.logger.info(f"[{self.name}] {stage}")
    
    def format_output(self, content: str, metadata: Dict) -> Dict[str, Any]:
        """Format agent output"""
        return {
            "content": content,
            "metadata": metadata,
            "timestamp": datetime.now().isoformat(),
            "agent": self.name
        }
```

### Agent 1: Code Analyzer Agent

```python
class CodeAnalyzerAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm, "code_analyzer")
    
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Analyze code structure and generate overview"""
        self.log_execution("Starting code analysis")
        
        # Extract structure
        structure = await self.extract_code_structure(
            state["repo_path"],
            state["language"]
        )
        
        state["code_structure"] = structure
        
        # Generate documentation
        prompt = f"""
        Generate a comprehensive overview and API documentation for this code structure:
        
        {json.dumps(structure, indent=2)}
        
        Include:
        1. Overview paragraph explaining the project
        2. Key classes and their responsibilities
        3. Main functions and their purposes
        4. Dependencies and imports
        5. Code organization
        
        Use clear, professional language.
        """
        
        overview_docs = await self.llm.ainvoke(prompt)
        
        return self.format_output(
            overview_docs.content,
            {"functions_found": len(structure.get("functions", [])),
             "classes_found": len(structure.get("classes", []))}
        )
    
    async def extract_code_structure(self, repo_path: str, language: str) -> Dict:
        """Extract code structure using AST"""
        if language == "python":
            return await self._analyze_python(repo_path)
        elif language == "javascript":
            return await self._analyze_javascript(repo_path)
        # ... other languages
    
    async def _analyze_python(self, repo_path: str) -> Dict:
        """Analyze Python code structure"""
        import ast
        import glob
        
        structure = {
            "functions": [],
            "classes": [],
            "modules": [],
            "imports": set()
        }
        
        # Find all Python files
        for file_path in glob.glob(f"{repo_path}/**/*.py", recursive=True):
            if "__pycache__" in file_path or ".venv" in file_path:
                continue
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    tree = ast.parse(content)
                
                rel_path = os.path.relpath(file_path, repo_path)
                structure["modules"].append(rel_path)
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef):
                        structure["functions"].append({
                            "name": node.name,
                            "file": rel_path,
                            "lineno": node.lineno,
                            "args": [arg.arg for arg in node.args.args],
                            "docstring": ast.get_docstring(node),
                            "decorators": [
                                d.id if isinstance(d, ast.Name) else str(d)
                                for d in node.decorator_list
                            ]
                        })
                    elif isinstance(node, ast.ClassDef):
                        structure["classes"].append({
                            "name": node.name,
                            "file": rel_path,
                            "lineno": node.lineno,
                            "docstring": ast.get_docstring(node),
                            "methods": [
                                n.name for n in node.body 
                                if isinstance(n, ast.FunctionDef)
                            ]
                        })
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            structure["imports"].add(alias.name)
            
            except Exception as e:
                self.logger.warning(f"Failed to parse {file_path}: {e}")
        
        structure["imports"] = list(structure["imports"])
        return structure
```

### Agent 2: Architecture Detective Agent

```python
class ArchitectureDetectiveAgent(BaseAgent):
    def __init__(self, llm, vectorstore):
        super().__init__(llm, "architecture_detective")
        self.vectorstore = vectorstore
    
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Detect and document system architecture"""
        self.log_execution("Analyzing architecture")
        
        # Analyze patterns
        patterns = await self.detect_patterns(state)
        
        # Retrieve similar architectures from RAG
        rag_context = await self.retrieve_architecture_context(patterns)
        
        # Generate architecture documentation
        prompt = f"""
        Based on the code structure and similar patterns, generate architecture documentation.
        
        Detected Patterns: {patterns}
        
        RAG Context (similar projects):
        {rag_context}
        
        Generate:
        1. Architecture Overview - Describe the overall structure
        2. Component Diagram (in ASCII) - Show relationships
        3. Design Patterns - Identify used patterns
        4. Layering - Frontend/Backend/Database layers if applicable
        5. Scalability Considerations - How does it scale?
        
        Be concise but comprehensive.
        """
        
        architecture_docs = await self.llm.ainvoke(prompt)
        
        return self.format_output(
            architecture_docs.content,
            {"patterns_detected": len(patterns)}
        )
    
    async def detect_patterns(self, state: DocState) -> List[str]:
        """Detect design patterns in code"""
        patterns = []
        
        # Check for common patterns
        structure = state["code_structure"]
        
        # Check for MVC/MVT
        has_models = any("model" in f.lower() for f in structure.get("modules", []))
        has_views = any("view" in f.lower() for f in structure.get("modules", []))
        has_controllers = any("controller" in f.lower() for f in structure.get("modules", []))
        
        if has_models and has_views:
            patterns.append("MVC/MVT Pattern")
        
        # Check for Factory pattern
        has_factory = any("factory" in c["name"].lower() 
                         for c in structure.get("classes", []))
        if has_factory:
            patterns.append("Factory Pattern")
        
        # Check for Singleton
        has_singleton = any("singleton" in c["name"].lower() 
                           for c in structure.get("classes", []))
        if has_singleton:
            patterns.append("Singleton Pattern")
        
        return patterns
    
    async def retrieve_architecture_context(self, patterns: List[str]) -> str:
        """Retrieve similar architecture patterns from RAG"""
        if not patterns:
            return ""
        
        query = f"Architecture with patterns: {', '.join(patterns)}"
        docs = await self.vectorstore.asimilarity_search(query, k=3)
        
        return "\n".join([doc.page_content for doc in docs])
```

### Agent 3: API Documentation Agent

```python
class APIDocumentationAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm, "api_documenter")
    
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Extract and document APIs"""
        self.log_execution("Generating API documentation")
        
        # Extract endpoints
        endpoints = await self.extract_endpoints(
            state["repo_path"],
            state["framework"]
        )
        
        # Generate OpenAPI schema
        openapi_schema = self.generate_openapi_schema(endpoints)
        state["openapi_schema"] = openapi_schema
        
        # Generate documentation
        prompt = f"""
        Generate comprehensive API documentation for these endpoints:
        
        {json.dumps(endpoints, indent=2)}
        
        Include for each endpoint:
        1. Description and purpose
        2. HTTP method and path
        3. Authentication requirements
        4. Request parameters and schemas
        5. Response examples (success and error cases)
        6. Rate limits if applicable
        
        Format as Markdown with code examples.
        """
        
        api_docs = await self.llm.ainvoke(prompt)
        
        return self.format_output(
            api_docs.content,
            {"endpoints_found": len(endpoints)}
        )
    
    async def extract_endpoints(self, repo_path: str, framework: str) -> List[Dict]:
        """Extract API endpoints based on framework"""
        endpoints = []
        
        if framework == "fastapi":
            endpoints = await self._extract_fastapi(repo_path)
        elif framework == "flask":
            endpoints = await self._extract_flask(repo_path)
        elif framework == "django":
            endpoints = await self._extract_django(repo_path)
        elif framework == "express":
            endpoints = await self._extract_express(repo_path)
        
        return endpoints
    
    async def _extract_fastapi(self, repo_path: str) -> List[Dict]:
        """Extract FastAPI endpoints"""
        import re
        
        endpoints = []
        
        for file_path in glob.glob(f"{repo_path}/**/*.py", recursive=True):
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                # Regex for FastAPI decorators
                pattern = r'@app\.(get|post|put|delete|patch|options)\s*\(\s*["\']([^"\']+)'
                
                for match in re.finditer(pattern, content):
                    method, path = match.groups()
                    endpoints.append({
                        "method": method.upper(),
                        "path": path,
                        "file": os.path.relpath(file_path, repo_path)
                    })
            except Exception as e:
                self.logger.warning(f"Failed to extract endpoints from {file_path}: {e}")
        
        return endpoints
    
    def generate_openapi_schema(self, endpoints: List[Dict]) -> Dict:
        """Generate OpenAPI 3.0.0 schema"""
        schema = {
            "openapi": "3.0.0",
            "info": {
                "title": "API Documentation",
                "version": "1.0.0"
            },
            "paths": {}
        }
        
        for endpoint in endpoints:
            path = endpoint["path"]
            method = endpoint["method"].lower()
            
            if path not in schema["paths"]:
                schema["paths"][path] = {}
            
            schema["paths"][path][method] = {
                "summary": f"{endpoint['method']} {path}",
                "responses": {
                    "200": {"description": "Success"},
                    "400": {"description": "Bad Request"},
                    "401": {"description": "Unauthorized"},
                    "500": {"description": "Internal Server Error"}
                }
            }
        
        return schema
```

### Agent 4: Examples Synthesizer Agent

```python
class ExamplesSynthesizerAgent(BaseAgent):
    def __init__(self, llm, vectorstore):
        super().__init__(llm, "examples_generator")
        self.vectorstore = vectorstore
    
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Generate usage examples"""
        self.log_execution("Generating examples")
        
        # Extract examples from repo
        repo_examples = await self.find_examples_in_repo(state["repo_path"])
        
        # Retrieve similar patterns from RAG
        rag_examples = await self.retrieve_example_patterns()
        
        # Generate documentation
        prompt = f"""
        Generate a "Quick Start" and "Examples" section with practical usage examples.
        
        Examples found in repo:
        {json.dumps(repo_examples[:3], indent=2)}
        
        Similar examples from RAG:
        {rag_examples}
        
        Create:
        1. Quick Start section (5 minutes to first working example)
        2. Common use cases (3-4 examples)
        3. Advanced usage examples
        4. Integration examples with popular libraries
        
        Use actual code from the project when possible.
        """
        
        examples_docs = await self.llm.ainvoke(prompt)
        
        return self.format_output(
            examples_docs.content,
            {"examples_extracted": len(repo_examples)}
        )
    
    async def find_examples_in_repo(self, repo_path: str) -> List[Dict]:
        """Find example files and code snippets"""
        examples = []
        
        # Look for example directories
        example_patterns = [
            "**/examples/**/*.py",
            "**/example/**/*.py",
            "**/demo/**/*.py",
            "**/samples/**/*.py",
            "**/test/**/*_example.py"
        ]
        
        for pattern in example_patterns:
            for file_path in glob.glob(f"{repo_path}/{pattern}", recursive=True):
                try:
                    with open(file_path, 'r') as f:
                        examples.append({
                            "file": os.path.relpath(file_path, repo_path),
                            "content": f.read()[:500]  # First 500 chars
                        })
                except Exception as e:
                    self.logger.warning(f"Failed to read {file_path}: {e}")
        
        return examples
    
    async def retrieve_example_patterns(self) -> str:
        """Retrieve similar examples from RAG"""
        query = "Code examples usage patterns"
        docs = await self.vectorstore.asimilarity_search(query, k=3)
        return "\n".join([doc.page_content for doc in docs])
```

### Agent 5: Consistency Validator Agent

```python
class ConsistencyValidatorAgent(BaseAgent):
    def __init__(self, llm):
        super().__init__(llm, "consistency_validator")
        self.quality_threshold = 3.5  # Out of 5
    
    async def invoke(self, state: DocState) -> Dict[str, Any]:
        """Validate and score documentation quality"""
        self.log_execution("Validating consistency")
        
        # Compile all documentation
        full_docs = self.compile_documentation(state)
        
        # Validate completeness
        completeness_score = await self.check_completeness(full_docs, state)
        
        # Check for consistency
        consistency_score = await self.check_consistency(full_docs)
        
        # Calculate overall quality
        quality_score = (completeness_score + consistency_score) / 2
        state["quality_score"] = quality_score
        
        # Generate validation report
        prompt = f"""
        Review this documentation and identify any gaps or improvements:
        
        Quality Metrics:
        - Completeness: {completeness_score}/5
        - Consistency: {consistency_score}/5
        - Overall: {quality_score}/5
        
        Documentation sections: {list(full_docs.keys())}
        
        Provide:
        1. Quality assessment
        2. Missing sections or information
        3. Suggestions for improvement
        4. Overall readiness assessment
        """
        
        validation = await self.llm.ainvoke(prompt)
        
        return self.format_output(
            validation.content,
            {"quality_score": quality_score}
        )
    
    def compile_documentation(self, state: DocState) -> Dict[str, str]:
        """Compile all documentation parts"""
        return {
            "overview": state.get("code_analysis_output", ""),
            "architecture": state.get("architecture_output", ""),
            "api": state.get("api_output", ""),
            "examples": state.get("examples_output", "")
        }
    
    async def check_completeness(self, docs: Dict[str, str], state: DocState) -> float:
        """Check if all required sections are present"""
        score = 0.0
        required_sections = ["overview", "api", "examples"]
        
        for section in required_sections:
            if section in docs and docs[section]:
                score += 1.0
        
        score = (score / len(required_sections)) * 5
        return min(score, 5.0)
    
    async def check_consistency(self, docs: Dict[str, str]) -> float:
        """Check consistency across sections"""
        # Simple heuristic: if all sections have similar length, they're consistent
        lengths = [len(content) for content in docs.values() if content]
        
        if not lengths:
            return 2.0
        
        avg_length = sum(lengths) / len(lengths)
        variance = sum((l - avg_length) ** 2 for l in lengths) / len(lengths)
        
        # Lower variance = higher consistency
        consistency = max(5.0 - (variance / 10000), 1.0)
        return consistency
```

---

## Tool Specifications

### Tool 1: Repository Analyzer

```python
@tool
async def analyze_repository(
    repo_path: str,
    language: str
) -> Dict[str, Any]:
    """
    Analyze repository structure and content.
    
    Args:
        repo_path: Path to cloned repository
        language: Programming language (python, javascript, java, go)
    
    Returns:
        Dictionary with structure, metrics, and metadata
    """
    return {
        "structure": {...},
        "metrics": {...},
        "language_version": {...}
    }
```

### Tool 2: Endpoint Extractor

```python
@tool
async def extract_api_endpoints(
    repo_path: str,
    framework: str
) -> List[Dict]:
    """
    Extract API endpoints from codebase.
    
    Args:
        repo_path: Repository path
        framework: Framework (fastapi, flask, django, express)
    
    Returns:
        List of endpoint definitions
    """
    pass
```

### Tool 3: Quality Scorer

```python
@tool
async def score_documentation_quality(
    documentation: str,
    metrics: Dict
) -> float:
    """
    Score documentation quality (1-5 scale).
    
    Args:
        documentation: Generated documentation
        metrics: Quality metrics
    
    Returns:
        Quality score
    """
    pass
```

---

## LangGraph Workflow

### Workflow State Definition

```python
from langgraph.graph import StateGraph
from typing import TypedDict, Dict, Any, List

class DocState(TypedDict):
    """State passed through documentation workflow"""
    
    # Input
    repo_url: str
    repo_path: str
    language: str
    framework: str
    formats: List[str]
    
    # Intermediate results
    code_structure: Dict[str, Any]
    code_analysis_output: str
    architecture_output: str
    api_output: str
    examples_output: str
    openapi_schema: Dict[str, Any]
    
    # Progress tracking
    current_stage: str
    progress: int
    
    # Final output
    final_documentation: Dict[str, str]  # format -> content
    quality_score: float
    
    # Error handling
    errors: List[str]
    retry_count: int
```

### Workflow Graph

```python
from langgraph.graph import StateGraph, END

def build_documentation_workflow() -> StateGraph:
    """Build the complete documentation generation workflow"""
    
    workflow = StateGraph(DocState)
    
    # Initialize agents
    llm = ChatAnthropic(model="claude-3-sonnet-20240229")
    vectorstore = await init_vectorstore()
    
    code_analyzer = CodeAnalyzerAgent(llm)
    architecture_detective = ArchitectureDetectiveAgent(llm, vectorstore)
    api_documenter = APIDocumentationAgent(llm)
    examples_generator = ExamplesSynthesizerAgent(llm, vectorstore)
    consistency_validator = ConsistencyValidatorAgent(llm)
    synthesizer = FinalSynthesizerAgent(llm)
    
    # Define async node functions
    async def node_code_analyzer(state: DocState) -> DocState:
        result = await code_analyzer.invoke(state)
        state["code_analysis_output"] = result["content"]
        state["progress"] = 20
        state["current_stage"] = "code_analysis"
        return state
    
    async def node_architecture(state: DocState) -> DocState:
        result = await architecture_detective.invoke(state)
        state["architecture_output"] = result["content"]
        state["progress"] = 40
        state["current_stage"] = "architecture_analysis"
        return state
    
    async def node_api_docs(state: DocState) -> DocState:
        result = await api_documenter.invoke(state)
        state["api_output"] = result["content"]
        state["progress"] = 60
        state["current_stage"] = "api_documentation"
        return state
    
    async def node_examples(state: DocState) -> DocState:
        result = await examples_generator.invoke(state)
        state["examples_output"] = result["content"]
        state["progress"] = 75
        state["current_stage"] = "examples_generation"
        return state
    
    async def node_validator(state: DocState) -> DocState:
        result = await consistency_validator.invoke(state)
        state["progress"] = 85
        state["current_stage"] = "quality_validation"
        return state
    
    async def node_synthesizer(state: DocState) -> DocState:
        result = await synthesizer.invoke(state)
        state["final_documentation"] = result["content"]
        state["progress"] = 95
        state["current_stage"] = "synthesis"
        return state
    
    # Add nodes
    workflow.add_node("code_analyzer", node_code_analyzer)
    workflow.add_node("architecture", node_architecture)
    workflow.add_node("api_docs", node_api_docs)
    workflow.add_node("examples", node_examples)
    workflow.add_node("validator", node_validator)
    workflow.add_node("synthesizer", node_synthesizer)
    workflow.add_node("cleanup", node_cleanup)
    
    # Define edges
    workflow.add_edge("START", "code_analyzer")
    
    # Parallel execution
    workflow.add_edge("code_analyzer", "architecture")
    workflow.add_edge("code_analyzer", "api_docs")
    workflow.add_edge("architecture", "examples")
    
    # Convergence
    workflow.add_edge("api_docs", "validator")
    workflow.add_edge("examples", "validator")
    
    # Final synthesis
    workflow.add_edge("validator", "synthesizer")
    workflow.add_edge("synthesizer", "cleanup")
    workflow.add_edge("cleanup", END)
    
    return workflow.compile()
```

### Workflow Execution

```python
async def execute_documentation_workflow(
    job_id: str,
    repo_url: str,
    formats: List[str],
    redis_client
) -> Dict[str, str]:
    """Execute the documentation generation workflow"""
    
    # Clone repository
    repo_path = await clone_repository(repo_url)
    detect_language = await detect_language_and_framework(repo_path)
    
    initial_state: DocState = {
        "repo_url": repo_url,
        "repo_path": repo_path,
        "language": detect_language["language"],
        "framework": detect_language["framework"],
        "formats": formats,
        "code_structure": {},
        "code_analysis_output": "",
        "architecture_output": "",
        "api_output": "",
        "examples_output": "",
        "openapi_schema": {},
        "current_stage": "initialization",
        "progress": 0,
        "final_documentation": {},
        "quality_score": 0.0,
        "errors": [],
        "retry_count": 0
    }
    
    workflow = build_documentation_workflow()
    
    try:
        # Execute workflow with progress updates
        async for output in workflow.astream(initial_state):
            # Update Redis with progress
            await redis_client.set(
                f"job:{job_id}:progress",
                json.dumps({
                    "progress": output.get("progress", 0),
                    "stage": output.get("current_stage", "")
                }),
                ex=86400
            )
            
            # Store intermediate outputs
            await redis_client.set(
                f"job:{job_id}:outputs",
                json.dumps({
                    format: output["final_documentation"].get(format, "")
                    for format in output["formats"]
                }),
                ex=86400
            )
        
        # Return final output
        return output["final_documentation"]
    
    except Exception as e:
        logger.error(f"Workflow execution failed for job {job_id}: {e}")
        raise
    
    finally:
        # Cleanup repository
        await cleanup_repository(repo_path)
```

---

## RAG Implementation

### Vector Store Initialization

```python
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.vectorstores import Pinecone
import pinecone

class RAGSystem:
    def __init__(self, pinecone_api_key: str, index_name: str = "autodoc"):
        self.embeddings = OpenAIEmbeddings(
            model="text-embedding-3-small"
        )
        self.index_name = index_name
        self.vectorstore = None
    
    async def initialize(self):
        """Initialize Pinecone connection"""
        pinecone.init(api_key=self.pinecone_api_key, environment="production")
        
        # Create or connect to index
        if self.index_name not in pinecone.list_indexes():
            pinecone.create_index(
                name=self.index_name,
                dimension=1536,
                metric="cosine"
            )
        
        self.vectorstore = Pinecone(
            pinecone.Index(self.index_name),
            self.embeddings,
            "text_key"
        )
    
    async def retrieve_examples(self, query: str, k: int = 3) -> List[str]:
        """Retrieve example patterns from vector store"""
        results = await self.vectorstore.asimilarity_search(query, k=k)
        return [doc.page_content for doc in results]
    
    async def retrieve_architecture_patterns(self, patterns: List[str]) -> str:
        """Retrieve similar architecture patterns"""
        query = f"Architecture patterns: {', '.join(patterns)}"
        results = await self.vectorstore.asimilarity_search(query, k=3)
        return "\n\n".join([doc.page_content for doc in results])
```

---

## Repository Manager

### Repository Operations

```python
import asyncio
import tempfile
from git import Repo

class RepositoryManager:
    def __init__(self, temp_base: str = "/tmp/autodoc"):
        self.temp_base = temp_base
        os.makedirs(temp_base, exist_ok=True)
    
    async def clone_repository(self, repo_url: str) -> str:
        """Clone GitHub repository"""
        try:
            # Generate unique folder
            job_id = str(uuid4())
            repo_path = os.path.join(self.temp_base, job_id)
            
            # Clone with timeout
            loop = asyncio.get_event_loop()
            await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    Repo.clone_from,
                    repo_url,
                    repo_path
                ),
                timeout=300  # 5 minutes
            )
            
            logger.info(f"Cloned repository to {repo_path}")
            return repo_path
        
        except Exception as e:
            logger.error(f"Failed to clone repository {repo_url}: {e}")
            raise RepositoryAccessError(str(e))
    
    async def detect_language(self, repo_path: str) -> Dict[str, str]:
        """Detect programming language and framework"""
        
        # Check file extensions
        extensions = await self._get_file_extensions(repo_path)
        
        language = "unknown"
        framework = "unknown"
        
        if extensions.get(".py", 0) > 0:
            language = "python"
            framework = await self._detect_python_framework(repo_path)
        elif extensions.get(".js", 0) > 0 or extensions.get(".ts", 0) > 0:
            language = "javascript"
            framework = await self._detect_js_framework(repo_path)
        elif extensions.get(".java", 0) > 0:
            language = "java"
            framework = "unknown"
        elif extensions.get(".go", 0) > 0:
            language = "go"
            framework = "unknown"
        
        return {
            "language": language,
            "framework": framework,
            "extensions": dict(extensions)
        }
    
    async def _detect_python_framework(self, repo_path: str) -> str:
        """Detect Python framework"""
        
        # Check requirements.txt or setup.py
        requirements_file = os.path.join(repo_path, "requirements.txt")
        
        if os.path.exists(requirements_file):
            with open(requirements_file, 'r') as f:
                content = f.read().lower()
                
                if "fastapi" in content:
                    return "fastapi"
                elif "flask" in content:
                    return "flask"
                elif "django" in content:
                    return "django"
        
        return "unknown"
    
    async def cleanup_repository(self, repo_path: str):
        """Delete cloned repository"""
        try:
            shutil.rmtree(repo_path)
            logger.info(f"Cleaned up repository at {repo_path}")
        except Exception as e:
            logger.error(f"Failed to cleanup repository: {e}")
    
    async def _get_file_extensions(self, repo_path: str) -> Dict[str, int]:
        """Count files by extension"""
        extensions = {}
        
        for root, _, files in os.walk(repo_path):
            if ".git" in root or "__pycache__" in root:
                continue
            
            for file in files:
                _, ext = os.path.splitext(file)
                extensions[ext] = extensions.get(ext, 0) + 1
        
        return extensions
```

---

## Error Handling & Retry Logic

### Error Classification

```python
class DocumentationError(Exception):
    """Base error"""
    http_status = 500
    retry = False

class RepositoryAccessError(DocumentationError):
    """Repository access failed"""
    http_status = 400
    retry = False

class RepositoryTooLargeError(DocumentationError):
    """Repository exceeds size limit"""
    http_status = 413
    retry = False

class CodeParsingError(DocumentationError):
    """Code parsing failed"""
    http_status = 422
    retry = True

class LLMError(DocumentationError):
    """LLM API error"""
    http_status = 503
    retry = True

class TimeoutError(DocumentationError):
    """Operation timed out"""
    http_status = 504
    retry = True
```

### Job Failure Handler

```python
class JobFailureHandler:
    def __init__(self, redis_client, max_retries: int = 2):
        self.redis = redis_client
        self.max_retries = max_retries
    
    async def handle_failure(self, job_id: str, error: Exception):
        """Handle job failure with retry logic"""
        
        # Get current retry count
        retry_count_str = await self.redis.get(f"job:{job_id}:retry_count")
        retry_count = int(retry_count_str or 0)
        
        if retry_count < self.max_retries and getattr(error, 'retry', False):
            # Schedule retry with exponential backoff
            delay = 2 ** retry_count  # 2, 4 seconds
            
            await self.redis.set(
                f"job:{job_id}:retry_count",
                str(retry_count + 1),
                ex=86400
            )
            
            # Re-queue job
            await celery_app.send_task(
                "tasks.generate_documentation",
                args=[job_id],
                countdown=delay
            )
            
            logger.info(f"Retrying job {job_id} in {delay} seconds")
        
        else:
            # Final failure
            await self.redis.set(
                f"job:{job_id}:status",
                "failed",
                ex=86400
            )
            
            await self.redis.set(
                f"job:{job_id}:error",
                json.dumps({
                    "code": error.__class__.__name__,
                    "message": str(error),
                    "http_status": getattr(error, 'http_status', 500)
                }),
                ex=86400
            )
            
            logger.error(f"Job {job_id} failed after {retry_count} retries")
```

---

## Testing Strategy

### Unit Tests

```python
import pytest

@pytest.mark.asyncio
async def test_code_analyzer_extracts_structure():
    """Test code structure extraction"""
    agent = CodeAnalyzerAgent(MockLLM())
    
    structure = await agent._analyze_python("/path/to/repo")
    
    assert "functions" in structure
    assert "classes" in structure
    assert len(structure["functions"]) > 0

@pytest.mark.asyncio
async def test_api_documenter_finds_endpoints():
    """Test endpoint extraction"""
    agent = APIDocumentationAgent(MockLLM())
    
    endpoints = await agent._extract_fastapi("/path/to/repo")
    
    assert isinstance(endpoints, list)
    assert all("method" in e and "path" in e for e in endpoints)

@pytest.mark.asyncio
async def test_validate_documentation_quality():
    """Test documentation quality scoring"""
    agent = ConsistencyValidatorAgent(MockLLM())
    
    docs = {
        "overview": "..." * 100,
        "api": "..." * 100,
        "examples": "..." * 100
    }
    
    score = await agent.check_completeness(docs, {})
    assert 1 <= score <= 5
```

### Integration Tests

```python
@pytest.mark.asyncio
async def test_full_workflow():
    """Test complete documentation generation"""
    
    repo_url = "https://github.com/test/sample-repo.git"
    
    # Execute workflow
    docs = await execute_documentation_workflow(
        job_id="test_job",
        repo_url=repo_url,
        formats=["markdown", "html"],
        redis_client=redis
    )
    
    # Verify outputs
    assert "markdown" in docs
    assert "html" in docs
    assert len(docs["markdown"]) > 100
```

---

## Code Structure & Patterns

### Directory Structure

```
autodocumentation-engine/
├── app/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app
│   ├── config.py                  # Configuration
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes.py              # API endpoints
│   │   └── schemas.py             # Pydantic schemas
│   │
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base_agent.py
│   │   ├── code_analyzer.py
│   │   ├── architecture_detective.py
│   │   ├── api_documenter.py
│   │   ├── examples_generator.py
│   │   └── consistency_validator.py
│   │
│   ├── workflows/
│   │   ├── __init__.py
│   │   ├── documentation_workflow.py
│   │   └── synthesizer.py
│   │
│   ├── rag/
│   │   ├── __init__.py
│   │   └── vector_store.py
│   │
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── repository_manager.py
│   │   └── job_manager.py
│   │
│   ├── generators/
│   │   ├── __init__.py
│   │   ├── markdown_generator.py
│   │   ├── html_generator.py
│   │   ├── pdf_generator.py
│   │   └── openapi_generator.py
│   │
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── validators.py
│   │
│   └── templates/
│       ├── markdown/
│       ├── html/
│       └── openapi/
│
├── tests/
│   ├── test_agents.py
│   ├── test_workflow.py
│   └── test_integration.py
│
├── docker/
│   ├── Dockerfile
│   └── docker-compose.yml
│
├── requirements.txt
├── .env.example
└── README.md
```

### Design Patterns

**Factory Pattern (Agent Creation)**:
```python
class AgentFactory:
    @staticmethod
    def create_agents(llm, vectorstore):
        return {
            "code_analyzer": CodeAnalyzerAgent(llm),
            "architecture": ArchitectureDetectiveAgent(llm, vectorstore),
            # ...
        }
```

**Strategy Pattern (Output Formatting)**:
```python
class OutputFormatter(ABC):
    @abstractmethod
    async def format(self, content: Dict) -> str:
        pass

class MarkdownFormatter(OutputFormatter):
    async def format(self, content: Dict) -> str:
        # Markdown specific formatting
        pass
```

---

## Conclusion

This LLD provides complete technical specifications for the simplified AutoDocumentation Engine. Key points:

✅ **Simple Flow**: GitHub URL → Analysis → Documentation  
✅ **No Persistence**: Temporary Redis storage only (24h TTL)  
✅ **Direct Output**: Multiple formats in single response  
✅ **Async Processing**: Job queue for scalability  
✅ **Fast Generation**: < 5 minutes average time  
✅ **Easy Deployment**: Stateless, horizontally scalable  

