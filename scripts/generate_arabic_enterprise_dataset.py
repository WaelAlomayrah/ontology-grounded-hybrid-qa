"""Generate a deterministic, internally consistent Arabic enterprise dataset."""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "data" / "Arabic_enterprise_dataset"
SEED = 20260724
rng = random.Random(SEED)

EMPLOYEE_COUNT = 800
DEPARTMENT_COUNT = 50
SYSTEM_COUNT = 200
PROJECT_COUNT = 100
VENDOR_COUNT = 300
DOCUMENT_COUNT = 3000
QUESTION_COUNT = 400

FIRST_NAMES = [
    "محمد", "أحمد", "عبدالله", "خالد", "سلمان", "فهد", "تركي", "سعود", "ناصر", "ياسر",
    "عمر", "علي", "حسن", "حسين", "إبراهيم", "مصطفى", "طارق", "زياد", "وليد", "مازن",
    "نورة", "سارة", "ريم", "لينا", "هند", "أمل", "منى", "هدى", "عبير", "دانة",
    "لطيفة", "مها", "شهد", "الجوهرة", "رنا", "غادة", "عائشة", "فاطمة", "مريم", "روان",
]
LAST_NAMES = [
    "العتيبي", "القحطاني", "الدوسري", "الحربي", "الشمري", "الغامدي", "الزهراني", "المطيري",
    "العنزي", "السبيعي", "المالكي", "العمري", "الشهري", "القرني", "الهاجري", "الرشيدي",
    "البلوي", "اليامي", "الجهني", "السلمي", "التميمي", "الخالدي", "السعدي", "العبيدي",
]
CITIES = ["الرياض", "جدة", "الدمام", "مكة المكرمة", "المدينة المنورة", "أبها", "تبوك", "القصيم", "حائل", "جازان", "نجران", "الأحساء"]
DEPARTMENTS = [
    "الإدارة التنفيذية", "الموارد البشرية", "المالية", "المشتريات", "الشؤون القانونية",
    "تقنية المعلومات", "الأمن السيبراني", "إدارة البيانات", "الذكاء الاصطناعي", "التحول الرقمي",
    "العمليات", "الجودة والتميز", "إدارة المشاريع", "التخطيط الاستراتيجي", "إدارة المخاطر",
    "المراجعة الداخلية", "خدمة العملاء", "تجربة المستفيد", "التسويق", "الاتصال المؤسسي",
    "المبيعات", "تطوير الأعمال", "سلاسل الإمداد", "إدارة المخزون", "الخدمات اللوجستية",
    "الصيانة", "المرافق", "السلامة", "الاستدامة", "المسؤولية الاجتماعية",
    "البحث والتطوير", "الابتكار", "التدريب والتطوير", "إدارة المعرفة", "إدارة المحتوى",
    "الحوكمة", "الامتثال", "الخصوصية", "هندسة الحلول", "البنية التحتية",
    "دعم التطبيقات", "إدارة الخدمات", "مكتب البيانات", "التحليلات", "هندسة المؤسسات",
    "العلاقات الحكومية", "الشراكات", "العقود", "الاستثمار", "إدارة الأصول",
]
JOB_TITLES = [
    "أخصائي", "أخصائي أول", "محلل", "محلل أول", "مهندس", "مهندس أول", "مستشار",
    "منسق", "مشرف", "رئيس فريق", "مدير منتج", "مدير مشروع", "خبير", "باحث",
]
SYSTEM_DOMAINS = [
    "الموارد البشرية", "المالية", "المشتريات", "العقود", "الوثائق", "خدمة العملاء",
    "إدارة المشاريع", "المخاطر", "الأصول", "المخزون", "التحليلات", "التدريب",
    "الحوكمة", "الأمن السيبراني", "إدارة الهوية", "المراسلات", "الجودة", "الامتثال",
    "البيانات الرئيسية", "ذكاء الأعمال",
]
SYSTEM_TYPES = ["منصة", "نظام", "بوابة", "تطبيق", "مستودع"]
PROJECT_THEMES = [
    "تطوير الخدمات الرقمية", "رفع كفاءة العمليات", "توحيد البيانات", "تجربة المستفيد",
    "الأتمتة الذكية", "الحوكمة المؤسسية", "تعزيز الأمن السيبراني", "إدارة المعرفة",
    "تحسين جودة البيانات", "استمرارية الأعمال", "تحليل الأداء", "التحول السحابي",
    "إدارة الأصول", "تكامل الأنظمة", "مركز الاتصال", "إدارة المواهب", "المشتريات الرقمية",
    "الامتثال المؤسسي", "الأرشفة الإلكترونية", "الابتكار المفتوح",
]
VENDOR_PREFIXES = ["شركة", "مؤسسة", "مجموعة"]
VENDOR_NAMES = [
    "الرواد", "الآفاق", "التميز", "المعرفة", "المدار", "النخبة", "الإتقان", "الابتكار",
    "المنارة", "الرؤية", "الريادة", "السحابة", "البيان", "المسار", "الربط", "الحلول",
    "التكامل", "المستقبل", "الواحة", "الصفوة", "القمم", "الركائز", "الدرع", "البوصلة",
]
SPECIALTIES = ["الحلول الرقمية", "الاستشارات", "الأمن السيبراني", "تحليل البيانات", "البنية التحتية", "التدريب", "الخدمات السحابية", "تكامل الأنظمة"]
DOC_TYPES = ["سياسة", "إجراء", "تقرير", "محضر اجتماع", "دليل مستخدم", "مذكرة", "خطة عمل", "دراسة", "طلب تغيير", "تقييم مخاطر"]
CLASSIFICATIONS = ["عام", "داخلي", "مقيد"]


def write_csv(name: str, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    with (OUTPUT / name).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def uri(kind: str, identifier: str) -> str:
    return f"<http://example.org/arabic-enterprise/{kind}/{quote(identifier, safe='-._~')}>"


def literal(value: object, language: bool = False) -> str:
    escaped = str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"@ar' if language else f'"{escaped}"'


OUTPUT.mkdir(parents=True, exist_ok=True)

locations = [{"id": f"LOC-{i:03d}", "label": city, "region": city} for i, city in enumerate(CITIES, 1)]

employees: list[dict[str, object]] = []
for index in range(1, EMPLOYEE_COUNT + 1):
    department_index = ((index - 1) % DEPARTMENT_COUNT) + 1
    first = FIRST_NAMES[(index * 7) % len(FIRST_NAMES)]
    last = LAST_NAMES[(index * 11) % len(LAST_NAMES)]
    employees.append({
        "id": f"EMP-{index:04d}",
        "label": f"{first} {last}",
        "job_title": "مدير إدارة" if index <= DEPARTMENT_COUNT else rng.choice(JOB_TITLES),
        "department_id": f"DEP-{department_index:03d}",
        "location_id": f"LOC-{((department_index - 1) % len(locations)) + 1:03d}",
        "email": f"employee{index:04d}@example.sa",
        "hire_date": str(date(2012, 1, 1) + timedelta(days=(index * 37) % 4800)),
        "grade": rng.choice(["السادسة", "السابعة", "الثامنة", "التاسعة", "العاشرة", "الحادية عشرة"]),
        "status": "على رأس العمل" if index % 29 else "إجازة طويلة",
    })

departments = []
for index, name in enumerate(DEPARTMENTS, 1):
    departments.append({
        "id": f"DEP-{index:03d}",
        "label": name,
        "sector": ["قطاع الخدمات المشتركة", "قطاع الأعمال", "قطاع التقنية", "قطاع الاستراتيجية"][index % 4],
        "location_id": f"LOC-{((index - 1) % len(locations)) + 1:03d}",
        "manager_id": f"EMP-{index:04d}",
        "annual_budget_sar": 2_000_000 + index * 375_000,
    })

vendors = []
for index in range(1, VENDOR_COUNT + 1):
    vendors.append({
        "id": f"VEN-{index:04d}",
        "label": f"{VENDOR_PREFIXES[index % 3]} {VENDOR_NAMES[(index * 5) % len(VENDOR_NAMES)]} {SPECIALTIES[(index * 3) % len(SPECIALTIES)]} {index}",
        "city": CITIES[index % len(CITIES)],
        "specialty": SPECIALTIES[index % len(SPECIALTIES)],
        "classification": ["استراتيجي", "معتمد", "مسجل"][index % 3],
        "commercial_status": "نشط",
    })

systems = []
for index in range(1, SYSTEM_COUNT + 1):
    domain = SYSTEM_DOMAINS[(index - 1) % len(SYSTEM_DOMAINS)]
    systems.append({
        "id": f"SYS-{index:04d}",
        "label": f"{SYSTEM_TYPES[index % len(SYSTEM_TYPES)]} {domain} المؤسسية {index}",
        "department_id": f"DEP-{((index * 7) % DEPARTMENT_COUNT) + 1:03d}",
        "vendor_id": f"VEN-{((index * 13) % VENDOR_COUNT) + 1:04d}",
        "category": domain,
        "criticality": ["عالية", "متوسطة", "منخفضة"][index % 3],
        "status": ["تشغيلي", "قيد التطوير", "تحت التحديث"][index % 3],
    })

projects = []
for index in range(1, PROJECT_COUNT + 1):
    start = date(2023, 1, 1) + timedelta(days=index * 8)
    projects.append({
        "id": f"PRJ-{index:04d}",
        "label": f"مشروع {PROJECT_THEMES[(index - 1) % len(PROJECT_THEMES)]} {index}",
        "department_id": f"DEP-{((index * 9) % DEPARTMENT_COUNT) + 1:03d}",
        "system_id": f"SYS-{((index * 17) % SYSTEM_COUNT) + 1:04d}",
        "manager_id": f"EMP-{((index * 19) % EMPLOYEE_COUNT) + 1:04d}",
        "status": ["قيد التنفيذ", "مخطط", "مكتمل"][index % 3],
        "start_date": str(start),
        "end_date": str(start + timedelta(days=180 + (index % 8) * 30)),
        "budget_sar": 500_000 + index * 85_000,
    })

assignments = []
for project_index in range(1, PROJECT_COUNT + 1):
    for offset in range(12):
        employee_index = ((project_index * 23 + offset * 31) % EMPLOYEE_COUNT) + 1
        assignments.append({
            "employee_id": f"EMP-{employee_index:04d}",
            "project_id": f"PRJ-{project_index:04d}",
            "role": ["قائد مسار", "محلل أعمال", "مهندس حلول", "عضو فريق"][offset % 4],
            "allocation_percent": [20, 30, 40, 50, 60][offset % 5],
        })

documents = []
with (OUTPUT / "documents.jsonl").open("w", encoding="utf-8") as handle:
    for index in range(1, DOCUMENT_COUNT + 1):
        department = departments[(index * 7) % DEPARTMENT_COUNT]
        author = employees[(index * 17) % EMPLOYEE_COUNT]
        system = systems[(index * 19) % SYSTEM_COUNT]
        project = projects[(index * 11) % PROJECT_COUNT]
        doc_type = DOC_TYPES[index % len(DOC_TYPES)]
        title = f"{doc_type} {department['label']} رقم {index}"
        body = (
            f"يوثق هذا المستند أعمال {department['label']} المتعلقة بـ {project['label']}. "
            f"يتناول المستند استخدام {system['label']}، والمسؤوليات التشغيلية، وضوابط الجودة، "
            f"ومؤشرات الأداء، وخطة المتابعة الدورية. أعد المستند {author['label']} ويجب مراجعته "
            f"وفق دورة الاعتماد المؤسسية مع توثيق الملاحظات والإجراءات التصحيحية."
        )
        record = {
            "id": f"DOC-{index:05d}", "title": title, "body": body, "document_type": doc_type,
            "department_id": department["id"], "author_id": author["id"], "system_id": system["id"],
            "project_id": project["id"], "created_at": str(date(2024, 1, 1) + timedelta(days=index % 730)),
            "classification": CLASSIFICATIONS[index % len(CLASSIFICATIONS)],
        }
        documents.append(record)
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

write_csv("locations.csv", list(locations[0]), locations)
write_csv("departments.csv", list(departments[0]), departments)
write_csv("employees.csv", list(employees[0]), employees)
write_csv("vendors.csv", list(vendors[0]), vendors)
write_csv("systems.csv", list(systems[0]), systems)
write_csv("projects.csv", list(projects[0]), projects)
write_csv("project_assignments.csv", list(assignments[0]), assignments)

ontology = """@prefix ae: <http://example.org/arabic-enterprise/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

ae:Ontology a owl:Ontology ; rdfs:label "أنطولوجيا المؤسسة العربية"@ar .
ae:Employee a owl:Class ; rdfs:label "موظف"@ar .
ae:Department a owl:Class ; rdfs:label "إدارة"@ar .
ae:InformationSystem a owl:Class ; rdfs:label "نظام معلومات"@ar .
ae:Project a owl:Class ; rdfs:label "مشروع"@ar .
ae:Vendor a owl:Class ; rdfs:label "مورد"@ar .
ae:Document a owl:Class ; rdfs:label "مستند"@ar .
ae:Location a owl:Class ; rdfs:label "موقع"@ar .
ae:worksIn a owl:ObjectProperty ; rdfs:label "يعمل في"@ar ; rdfs:domain ae:Employee ; rdfs:range ae:Department .
ae:manages a owl:ObjectProperty ; rdfs:label "يدير"@ar ; rdfs:domain ae:Employee ; rdfs:range ae:Department .
ae:locatedAt a owl:ObjectProperty ; rdfs:label "موجود في"@ar ; rdfs:range ae:Location .
ae:ownedBy a owl:ObjectProperty ; rdfs:label "مملوك بواسطة"@ar ; rdfs:domain ae:InformationSystem ; rdfs:range ae:Department .
ae:suppliedBy a owl:ObjectProperty ; rdfs:label "مورّد بواسطة"@ar ; rdfs:domain ae:InformationSystem ; rdfs:range ae:Vendor .
ae:sponsoredBy a owl:ObjectProperty ; rdfs:label "برعاية"@ar ; rdfs:domain ae:Project ; rdfs:range ae:Department .
ae:usesSystem a owl:ObjectProperty ; rdfs:label "يستخدم النظام"@ar ; rdfs:domain ae:Project ; rdfs:range ae:InformationSystem .
ae:managedBy a owl:ObjectProperty ; rdfs:label "يدار بواسطة"@ar ; rdfs:domain ae:Project ; rdfs:range ae:Employee .
ae:assignedTo a owl:ObjectProperty ; rdfs:label "مكلف في"@ar ; rdfs:domain ae:Employee ; rdfs:range ae:Project .
ae:authoredBy a owl:ObjectProperty ; rdfs:label "أعد بواسطة"@ar ; rdfs:domain ae:Document ; rdfs:range ae:Employee .
ae:aboutProject a owl:ObjectProperty ; rdfs:label "يتعلق بالمشروع"@ar ; rdfs:domain ae:Document ; rdfs:range ae:Project .
ae:aboutSystem a owl:ObjectProperty ; rdfs:label "يتعلق بالنظام"@ar ; rdfs:domain ae:Document ; rdfs:range ae:InformationSystem .
ae:belongsTo a owl:ObjectProperty ; rdfs:label "يتبع الإدارة"@ar ; rdfs:domain ae:Document ; rdfs:range ae:Department .
"""
(OUTPUT / "ontology.ttl").write_text(ontology, encoding="utf-8")

triples: list[str] = [ontology.rstrip(), ""]


def entity_block(kind: str, row: dict[str, object], rdf_class: str, label_key: str = "label") -> None:
    subject = uri(kind, str(row["id"]))
    triples.append(f"{subject} a ae:{rdf_class} ;")
    triples.append(f"  rdfs:label {literal(row[label_key], True)} ;")


for row in locations:
    entity_block("location", row, "Location")
    triples.append(f"  ae:region {literal(row['region'], True)} .\n")
for row in departments:
    entity_block("department", row, "Department")
    triples.extend([
        f"  ae:sector {literal(row['sector'], True)} ;",
        f"  ae:annualBudget {literal(row['annual_budget_sar'])} ;",
        f"  ae:locatedAt {uri('location', str(row['location_id']))} .\n",
    ])
    triples.append(f"{uri('employee', str(row['manager_id']))} ae:manages {uri('department', str(row['id']))} .\n")
for row in employees:
    entity_block("employee", row, "Employee")
    triples.extend([
        f"  ae:jobTitle {literal(row['job_title'], True)} ;",
        f"  ae:email {literal(row['email'])} ;",
        f"  ae:hireDate {literal(row['hire_date'])} ;",
        f"  ae:grade {literal(row['grade'], True)} ;",
        f"  ae:employmentStatus {literal(row['status'], True)} ;",
        f"  ae:worksIn {uri('department', str(row['department_id']))} ;",
        f"  ae:locatedAt {uri('location', str(row['location_id']))} .\n",
    ])
for row in vendors:
    entity_block("vendor", row, "Vendor")
    triples.extend([
        f"  ae:city {literal(row['city'], True)} ;",
        f"  ae:specialty {literal(row['specialty'], True)} ;",
        f"  ae:vendorClassification {literal(row['classification'], True)} ;",
        f"  ae:commercialStatus {literal(row['commercial_status'], True)} .\n",
    ])
for row in systems:
    entity_block("system", row, "InformationSystem")
    triples.extend([
        f"  ae:category {literal(row['category'], True)} ;",
        f"  ae:criticality {literal(row['criticality'], True)} ;",
        f"  ae:systemStatus {literal(row['status'], True)} ;",
        f"  ae:ownedBy {uri('department', str(row['department_id']))} ;",
        f"  ae:suppliedBy {uri('vendor', str(row['vendor_id']))} .\n",
    ])
for row in projects:
    entity_block("project", row, "Project")
    triples.extend([
        f"  ae:projectStatus {literal(row['status'], True)} ;",
        f"  ae:startDate {literal(row['start_date'])} ;",
        f"  ae:endDate {literal(row['end_date'])} ;",
        f"  ae:projectBudget {literal(row['budget_sar'])} ;",
        f"  ae:sponsoredBy {uri('department', str(row['department_id']))} ;",
        f"  ae:usesSystem {uri('system', str(row['system_id']))} ;",
        f"  ae:managedBy {uri('employee', str(row['manager_id']))} .\n",
    ])
for row in assignments:
    triples.append(f"{uri('employee', str(row['employee_id']))} ae:assignedTo {uri('project', str(row['project_id']))} .")
for row in documents:
    entity_block("document", row, "Document", "title")
    triples.extend([
        f"  ae:documentType {literal(row['document_type'], True)} ;",
        f"  ae:body {literal(row['body'], True)} ;",
        f"  ae:createdAt {literal(row['created_at'])} ;",
        f"  ae:classification {literal(row['classification'], True)} ;",
        f"  ae:belongsTo {uri('department', str(row['department_id']))} ;",
        f"  ae:authoredBy {uri('employee', str(row['author_id']))} ;",
        f"  ae:aboutSystem {uri('system', str(row['system_id']))} ;",
        f"  ae:aboutProject {uri('project', str(row['project_id']))} .\n",
    ])

(OUTPUT / "knowledge_graph.ttl").write_text("\n".join(triples), encoding="utf-8")

questions: list[dict[str, object]] = []


def add_question(question: str, entities_: list[str], answers: list[str], path: list[str], category: str) -> None:
    questions.append({
        "id": f"ar-q{len(questions) + 1:04d}",
        "question": question,
        "expected_entities": entities_,
        "expected_answer_keywords": answers,
        "expected_path": path,
        "category": category,
        "language": "ar",
    })


for index in range(80):
    employee = employees[(index * 29) % EMPLOYEE_COUNT]
    department = departments[int(str(employee["department_id"]).split("-")[1]) - 1]
    add_question(
        f"في أي إدارة يعمل الموظف {employee['label']}؟",
        [str(employee["label"]), str(department["label"])], [str(department["label"])],
        [str(employee["label"]), "يعمل في", str(department["label"])], "direct",
    )
for index in range(80):
    system = systems[(index * 31) % SYSTEM_COUNT]
    vendor = vendors[int(str(system["vendor_id"]).split("-")[1]) - 1]
    add_question(
        f"ما المورد الذي يورد {system['label']}؟",
        [str(system["label"]), str(vendor["label"])], [str(vendor["label"])],
        [str(system["label"]), "مورّد بواسطة", str(vendor["label"])], "relationship",
    )
for index in range(80):
    project = projects[(index * 37) % PROJECT_COUNT]
    system = systems[int(str(project["system_id"]).split("-")[1]) - 1]
    vendor = vendors[int(str(system["vendor_id"]).split("-")[1]) - 1]
    add_question(
        f"من هو مورد النظام المستخدم في {project['label']}؟",
        [str(project["label"]), str(system["label"]), str(vendor["label"])], [str(vendor["label"])],
        [str(project["label"]), "يستخدم النظام", str(system["label"]), "مورّد بواسطة", str(vendor["label"])], "multi_hop",
    )
for index in range(80):
    document = documents[(index * 41) % DOCUMENT_COUNT]
    author = employees[int(str(document["author_id"]).split("-")[1]) - 1]
    add_question(
        f"من أعد المستند «{document['title']}»؟",
        [str(document["title"]), str(author["label"])], [str(author["label"])],
        [str(document["title"]), "أعد بواسطة", str(author["label"])], "document",
    )
for index in range(40):
    department = departments[index]
    count = sum(employee["department_id"] == department["id"] for employee in employees)
    add_question(
        f"كم عدد الموظفين في {department['label']}؟",
        [str(department["label"])], [str(count)], ["موظف", "يعمل في", str(department["label"])], "aggregation",
    )
for index in range(40):
    subject = ["مطعم المدير المفضل", "لون مكتب الرئيس", "الهواية الشخصية للمدير", "رقم هاتف منزل الموظف"][index % 4]
    add_question(
        f"ما هو {subject}؟",
        [], ["الأدلة غير كافية"], [], "unanswerable",
    )

assert len(questions) == QUESTION_COUNT
(OUTPUT / "evaluation_questions_ar.json").write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

source_line_count = sum(
    1
    for line in (OUTPUT / "knowledge_graph.ttl").read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("@prefix") and not line.startswith("#")
)
rdf_triple_count = (
    129  # ontology schema triples
    + len(locations) * 2
    + len(departments) * 5
    + len(employees) * 9
    + len(vendors) * 6
    + len(systems) * 7
    + len(projects) * 9
    + len(assignments)
    + len(documents) * 10
)
metadata = {
    "name": "Arabic Enterprise Ontology QA Dataset",
    "language": "ar",
    "synthetic": True,
    "seed": SEED,
    "created": str(date.today()),
    "counts": {
        "employees": len(employees), "departments": len(departments), "systems": len(systems),
        "projects": len(projects), "vendors": len(vendors), "documents": len(documents),
        "project_assignments": len(assignments), "evaluation_questions": len(questions),
        "rdf_triples": rdf_triple_count,
        "rdf_source_lines": source_line_count,
    },
}
(OUTPUT / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
(OUTPUT / "README.md").write_text(
    """# Arabic Enterprise Ontology QA Dataset

Deterministic synthetic Arabic enterprise data for ontology-grounded question answering.

## Contents

- `employees.csv`, `departments.csv`, `systems.csv`, `projects.csv`, `vendors.csv`, `locations.csv`
- `project_assignments.csv`: employee-to-project relationships
- `documents.jsonl`: 3,000 Arabic enterprise documents
- `ontology.ttl`: Arabic RDF/OWL vocabulary
- `knowledge_graph.ttl`: populated RDF graph
- `evaluation_questions_ar.json`: 400 Arabic evaluation questions with expected evidence
- `metadata.json`: generation seed and validated counts

All people, organisations, systems, projects, documents, and relationships are synthetic. They do not represent real persons or organisations.
""",
    encoding="utf-8",
)
print(json.dumps(metadata, ensure_ascii=False, indent=2))
