"""Educational & Professional Streams and Difficulty Mappings"""
from typing import List

STREAMS = {
    "Computer Science": ["Core CS & Algorithms", "OOP", "OS & Architecture", "DBMS"],
    "Information Technology": ["Enterprise Systems", "IT Infrastructure", "Systems Admin"],
    "Artificial Intelligence": ["Generative AI & LLMs", "Deep Learning", "Computer Vision", "NLP"],
    "Machine Learning": ["Supervised & Unsupervised Learning", "Feature Engineering", "MLOps"],
    "Data Science": ["Python & Statistical Modeling", "EDA", "Hypothesis Testing", "Big Data"],
    "Data Analytics": ["SQL & Advanced Querying", "Tableau / PowerBI", "Quantitative Analysis"],
    "Data Engineering": ["ETL / ELT Pipelines", "Spark & Kafka", "Data Warehousing", "Airflow"],
    "Web Development": ["Frontend (React/Next)", "Backend (FastAPI/Node)", "Full Stack"],
    "Software Development": ["Python Engineering", "Java / Spring Boot", "Design Patterns"],
    "Cybersecurity": ["Network Security", "Penetration Testing", "Ethical Hacking"],
    "Cloud Computing": ["AWS Architecture", "Azure", "GCP", "Docker & Kubernetes"],
    "Electronics and Communication": ["Embedded Systems", "Signal Processing", "IoT", "VLSI"],
    "Mechanical Engineering": ["Thermodynamics", "Machine Design", "CAD / CAM", "Robotics"],
    "Civil Engineering": ["Structural Analysis", "Geotechnical", "Project Management"],
    "Electrical Engineering": ["Power Systems", "Control Systems", "EVs & Drives"],
    "Business and Management": ["Strategic Planning", "Supply Chain", "Product Management"],
    "Finance": ["Financial Modeling", "Corporate Finance", "Investment Banking"],
    "Marketing": ["Digital Marketing & SEO", "Brand Strategy", "Market Research"],
    "Human Resources": ["Talent Acquisition", "HR Operations", "Employee Engagement"],
    "Other": ["General Technical Domain", "Cross-Disciplinary Field"],
}

EXPERIENCE_LEVELS = [
    "Fresher / Student (0 years)",
    "Entry-Level (1-2 years)",
    "Mid-Level (3-5 years)",
    "Senior (5+ years)",
]

INTERVIEW_TYPES = [
    "Technical Assessment",
    "Conceptual & Foundational",
    "System Design & Architecture",
]

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]

EXPERIENCE_TO_DIFFICULTY = {
    "Fresher / Student (0 years)": "Beginner",
    "Entry-Level (1-2 years)": "Beginner",
    "Mid-Level (3-5 years)": "Intermediate",
    "Senior (5+ years)": "Advanced",
    "Fresher": "Beginner",
    "Junior": "Beginner",
    "Mid": "Intermediate",
    "Senior": "Advanced",
}

_STREAM_FAMILIES = {
    "Data Science": ["Data Science", "Machine Learning", "Artificial Intelligence", "Data Analytics", "Computer Science"],
    "Machine Learning": ["Machine Learning", "Artificial Intelligence", "Data Science", "Computer Science"],
    "Artificial Intelligence": ["Artificial Intelligence", "Machine Learning", "Data Science", "Computer Science"],
    "Data Analytics": ["Data Analytics", "Data Science", "Computer Science"],
    "Software Development": ["Software Development", "Computer Science", "Web Development"],
    "Computer Science": ["Computer Science", "Software Development", "Web Development"],
}

def family_streams(stream: str) -> List[str]:
    return _STREAM_FAMILIES.get(stream, [stream, "Computer Science", "Other"])