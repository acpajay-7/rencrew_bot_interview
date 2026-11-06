"""Streams, specializations, experience levels, interview types."""
STREAMS = {
    "Computer Science": ["Data Structures and Algorithms", "Operating Systems", "DBMS", "Computer Networks",
                         "Software Engineering", "Artificial Intelligence", "Machine Learning", "Web Development"],
    "Information Technology": ["Programming", "DBMS", "Computer Networks", "Web Development", "Software Engineering"],
    "Artificial Intelligence": ["Machine Learning", "Deep Learning", "NLP", "Generative AI", "LLMs"],
    "Machine Learning": ["Supervised Learning", "Model Evaluation", "Feature Engineering", "Deep Learning"],
    "Data Science": ["Python", "SQL", "Statistics", "Data Analysis", "Exploratory Data Analysis",
                     "Machine Learning", "Deep Learning", "NLP", "Data Visualization", "Generative AI", "LLMs"],
    "Data Analytics": ["SQL", "Data Analysis", "Data Visualization", "Statistics"],
    "Data Engineering": ["SQL", "ETL", "Data Warehousing", "Big Data"],
    "Web Development": ["Frontend", "Backend", "Databases", "APIs"],
    "Software Development": ["Programming", "Data Structures and Algorithms", "Software Engineering", "Databases"],
    "Cybersecurity": ["Network Security", "Cryptography", "Web Security"],
    "Cloud Computing": ["Cloud Fundamentals", "Containers and DevOps", "Cloud Networking"],
    "Electronics and Communication": ["Analog Electronics", "Digital Electronics", "Communication Systems"],
    "Mechanical Engineering": ["Thermodynamics", "Fluid Mechanics", "Machine Design"],
    "Civil Engineering": ["Structural Engineering", "Geotechnical Engineering", "Construction Management"],
    "Electrical Engineering": ["Circuits", "Power Systems", "Machines"],
    "Business and Management": ["Management Fundamentals", "Strategy", "Operations"],
    "Finance": ["Corporate Finance", "Accounting", "Markets"],
    "Marketing": ["Digital Marketing", "Consumer Behaviour", "Branding"],
    "Human Resources": ["Recruitment", "Employee Relations", "Compensation"],
    "Other": [],
}

# Streams that share one question pool. Questions are NEVER pulled from outside a family.
FAMILIES = {
    "data_ai": {"Data Science", "Machine Learning", "Artificial Intelligence", "Data Analytics", "Data Engineering"},
    "software": {"Computer Science", "Information Technology", "Web Development", "Software Development"},
}


def family_streams(stream: str) -> set:
    for members in FAMILIES.values():
        if stream in members:
            return set(members)
    return {stream}


EXPERIENCE_LEVELS = ["Student", "Fresher", "Internship Level", "Entry Level", "Intermediate", "Experienced Professional"]
DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]
EXPERIENCE_TO_DIFFICULTY = {
    "Student": ["Beginner"],
    "Fresher": ["Beginner", "Intermediate"],
    "Internship Level": ["Beginner", "Intermediate"],
    "Entry Level": ["Beginner", "Intermediate"],
    "Intermediate": ["Intermediate", "Advanced", "Beginner"],
    "Experienced Professional": ["Advanced", "Intermediate"],
}
INTERVIEW_TYPES = ["Technical Interview", "Conceptual Interview", "HR / Behavioural Interview", "Mixed Interview"]
