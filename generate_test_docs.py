"""Generate test documents for aggressive testing of Full Context + Reranker."""

# ============================================================
# 1. MEDIUM English doc (~15K chars) - Full Context mode
# ============================================================
en_medium = """# Company Employee Handbook - TechVision Inc.

## Chapter 1: Company Overview

TechVision Inc. was founded in 2015 by Dr. Sarah Mitchell and James Rodriguez in Austin, Texas.
The company specializes in artificial intelligence solutions for healthcare, serving over 200 hospitals
across North America. Our annual revenue reached $45 million in 2024, with a workforce of 380 employees.

### Mission Statement
To revolutionize healthcare through intelligent automation, reducing diagnostic errors by 40% and
improving patient outcomes across all demographics.

### Core Values
1. Innovation First - We invest 22% of revenue in R&D
2. Patient Safety - Zero tolerance for untested deployments
3. Diversity & Inclusion - 47% of leadership positions held by underrepresented groups
4. Transparency - Quarterly town halls and open-door policy

## Chapter 2: Employment Policies

### 2.1 Working Hours
Standard working hours are Monday through Friday, 9:00 AM to 5:30 PM local time.
- Core hours (mandatory presence): 10:00 AM - 3:00 PM
- Flexible start: between 7:00 AM and 10:00 AM
- Remote work: Up to 3 days per week (approval required for full remote)

### 2.2 Leave Policy
Annual leave allocation by tenure:
| Tenure | Annual Leave | Sick Leave | Personal Days |
|--------|-------------|------------|---------------|
| 0-1 years | 15 days | 10 days | 3 days |
| 1-3 years | 20 days | 10 days | 4 days |
| 3-5 years | 25 days | 12 days | 5 days |
| 5+ years | 30 days | 15 days | 5 days |

Carry-over: Maximum 5 unused annual leave days may be carried to next year.
Parental leave: 16 weeks paid (primary caregiver), 8 weeks paid (secondary caregiver).

### 2.3 Compensation Structure
Base salary ranges by level:
- Junior Engineer (L1-L2): $75,000 - $95,000
- Mid-Level Engineer (L3-L4): $100,000 - $135,000
- Senior Engineer (L5-L6): $140,000 - $180,000
- Staff Engineer (L7): $185,000 - $220,000
- Principal Engineer (L8): $225,000 - $280,000
- Distinguished Engineer (L9): $285,000 - $350,000

Annual bonus: 10-25% of base salary based on performance rating.
Stock options vest over 4 years with a 1-year cliff.

## Chapter 3: Benefits

### 3.1 Health Insurance
- Medical: BlueCross BlueShield PPO (company covers 85% of premium)
- Dental: Delta Dental (company covers 100%)
- Vision: VSP Choice Plan (company covers 100%)
- Mental Health: 12 free therapy sessions per year through BetterHelp partnership

### 3.2 Retirement
- 401(k) with 6% company match (immediate vesting)
- Financial planning consultation: 2 free sessions per year with certified advisor

### 3.3 Professional Development
- Annual learning budget: $3,000 per employee
- Conference attendance: Up to 2 conferences per year (company-funded)
- Internal mentorship program with quarterly check-ins
- Tuition reimbursement: Up to $10,000/year for job-related degrees

## Chapter 4: Performance Reviews

### 4.1 Review Cycle
Performance reviews occur bi-annually:
- Mid-year review: June (development-focused, no rating)
- Annual review: December (rating + compensation adjustment)

### 4.2 Rating Scale
1. Needs Improvement - Below expectations, PIP may be initiated
2. Meets Expectations - Solid performance, standard raise (3-5%)
3. Exceeds Expectations - Strong contributor, above-average raise (6-10%)
4. Outstanding - Top performer, significant raise + bonus multiplier (11-15%)
5. Exceptional - Rare, reserved for transformative contributions (16-25%)

### 4.3 Promotion Criteria
Promotions require:
- Minimum 12 months at current level
- Consistent "Exceeds" or higher ratings
- Demonstrated impact at next level
- Sponsor from leadership team
- Technical review panel approval (for engineering roles)

## Chapter 5: IT & Security Policies

### 5.1 Equipment
All employees receive:
- MacBook Pro 16" (M3 Pro) or equivalent Dell XPS (employee choice)
- 27" 4K monitor for home office
- Ergonomic keyboard and mouse
- $500 home office setup stipend (one-time)

### 5.2 Data Security
- All laptops must have FileVault/BitLocker encryption enabled
- Two-factor authentication required for all company systems
- VPN required when accessing internal systems remotely
- Patient data (PHI) must never be stored on local machines
- Security training: Mandatory quarterly modules (KnowBe4)

### 5.3 Acceptable Use
- Company devices may be used for reasonable personal use
- No cryptocurrency mining on company hardware
- No installation of unauthorized software without IT approval
- Report any security incidents within 1 hour to security@techvision.com

## Chapter 6: Travel & Expenses

### 6.1 Travel Policy
- Domestic flights: Economy class (Business class for flights > 6 hours)
- International flights: Business class
- Hotels: Up to $250/night domestic, $350/night international
- Per diem: $75/day domestic, $100/day international
- Car rental: Intermediate class or equivalent

### 6.2 Expense Reporting
- Submit within 14 days of expense
- Receipts required for all expenses over $25
- Manager approval required for expenses over $500
- Finance review for expenses over $2,000

## Chapter 7: Office Locations

### Austin HQ (Main Office)
- Address: 500 Innovation Blvd, Austin, TX 78701
- Capacity: 250 employees
- Amenities: Cafeteria, gym, meditation room, rooftop garden
- Parking: Free garage parking for all employees

### Boston R&D Center
- Address: 100 Cambridge St, Boston, MA 02142
- Capacity: 80 employees
- Focus: AI Research and Model Development

### San Francisco Sales Office
- Address: 44 Montgomery St, Suite 1200, San Francisco, CA 94104
- Capacity: 50 employees
- Focus: West Coast sales and partnerships

## Appendix A: Key Contacts
| Department | Contact | Email | Phone |
|-----------|---------|-------|-------|
| HR | Maria Chen | hr@techvision.com | (512) 555-0101 |
| IT Support | David Park | it@techvision.com | (512) 555-0102 |
| Finance | Lisa Thompson | finance@techvision.com | (512) 555-0103 |
| Legal | Robert Kim | legal@techvision.com | (512) 555-0104 |
| Facilities | Ana Gutierrez | facilities@techvision.com | (512) 555-0105 |
| Security | James Wilson | security@techvision.com | (512) 555-0106 |

Last updated: January 15, 2025
Version: 3.2
"""

with open('/tmp/test_handbook_en.txt', 'w', encoding='utf-8') as f:
    f.write(en_medium)
print(f"Medium English doc: {len(en_medium):,} chars")


# ============================================================
# 2. MEDIUM Arabic doc (~12K chars) - Full Context mode
# ============================================================
ar_medium = """# دليل الموظفين - شركة رؤية التقنية

## الفصل الأول: نظرة عامة على الشركة

تأسست شركة رؤية التقنية في عام 2018 على يد المهندس أحمد الراشدي والدكتورة فاطمة المنصوري في دبي، الإمارات العربية المتحدة.
تتخصص الشركة في حلول الذكاء الاصطناعي للقطاع المالي والمصرفي، وتخدم أكثر من 150 مؤسسة مالية في منطقة الشرق الأوسط وشمال أفريقيا.
بلغت إيرادات الشركة السنوية 120 مليون درهم في عام 2024، مع قوة عاملة تضم 250 موظفاً.

### الرؤية
أن نكون الشريك التقني الأول للمؤسسات المالية في المنطقة العربية.

### القيم الأساسية
1. الابتكار المستمر - نستثمر 18% من الإيرادات في البحث والتطوير
2. أمن البيانات - التزام صارم بمعايير الحماية الدولية
3. خدمة العملاء - دعم فني على مدار الساعة طوال أيام الأسبوع
4. تطوير الكفاءات - برامج تدريب مستمرة لجميع الموظفين

## الفصل الثاني: سياسات التوظيف

### 2.1 ساعات العمل
ساعات العمل الرسمية من الأحد إلى الخميس، من الساعة 8:00 صباحاً حتى 4:30 مساءً.
- ساعات الحضور الإلزامي: 9:00 صباحاً - 2:00 مساءً
- بداية مرنة: بين 7:00 و 9:00 صباحاً
- العمل عن بُعد: يومان في الأسبوع (بموافقة المدير المباشر)
- خلال شهر رمضان: تُخفَّض ساعات العمل بمقدار ساعتين يومياً

### 2.2 سياسة الإجازات
تخصيص الإجازات حسب سنوات الخدمة:
| سنوات الخدمة | إجازة سنوية | إجازة مرضية | إجازة شخصية |
|-------------|------------|------------|-------------|
| أقل من سنة | 22 يوم | 15 يوم | 3 أيام |
| 1-3 سنوات | 25 يوم | 15 يوم | 4 أيام |
| 3-5 سنوات | 28 يوم | 20 يوم | 5 أيام |
| أكثر من 5 سنوات | 30 يوم | 20 يوم | 5 أيام |

إجازة الحج: 15 يوم (مرة واحدة خلال فترة الخدمة)
إجازة الأمومة: 60 يوم مدفوعة الأجر
إجازة الأبوة: 5 أيام مدفوعة الأجر
إجازة الزواج: 5 أيام مدفوعة الأجر
إجازة الوفاة: 3-5 أيام حسب درجة القرابة

### 2.3 هيكل الرواتب
نطاقات الرواتب الأساسية حسب المستوى (بالدرهم الإماراتي شهرياً):
- مهندس مبتدئ (المستوى 1-2): 12,000 - 18,000 درهم
- مهندس متوسط (المستوى 3-4): 20,000 - 30,000 درهم
- مهندس أول (المستوى 5-6): 32,000 - 45,000 درهم
- مهندس رئيسي (المستوى 7): 48,000 - 60,000 درهم
- مدير تقني (المستوى 8): 55,000 - 75,000 درهم
- نائب رئيس التقنية (المستوى 9): 80,000 - 120,000 درهم

مكافأة نهاية الخدمة: حسب قانون العمل الإماراتي
بدل سكن: 30% من الراتب الأساسي
بدل مواصلات: 2,500 درهم شهرياً
بدل تعليم الأبناء: حتى 50,000 درهم سنوياً (لكل طفل، بحد أقصى 3 أطفال)

## الفصل الثالث: المزايا والتأمينات

### 3.1 التأمين الصحي
- تأمين طبي شامل (يغطي الموظف وعائلته حتى 4 أفراد)
- تأمين أسنان بحد أقصى 10,000 درهم سنوياً
- تأمين بصر بحد أقصى 3,000 درهم سنوياً
- تغطية الأمراض المزمنة والعمليات الجراحية
- برنامج صحة نفسية: 8 جلسات مجانية سنوياً

### 3.2 التطوير المهني
- ميزانية تدريب سنوية: 15,000 درهم لكل موظف
- حضور المؤتمرات: مؤتمران سنوياً (تتحمل الشركة التكاليف)
- شهادات مهنية: تتحمل الشركة 100% من تكلفة الشهادات المعتمدة
- برنامج الماجستير: دعم حتى 80,000 درهم سنوياً

### 3.3 بدلات إضافية
- تذاكر طيران سنوية: تذكرة ذهاب وعودة للموظف وعائلته
- مكافأة أداء سنوية: 1-4 رواتب حسب التقييم
- بدل هاتف: 500 درهم شهرياً
- عضوية نادي رياضي: حتى 5,000 درهم سنوياً

## الفصل الرابع: تقييم الأداء

### 4.1 دورة التقييم
يتم تقييم الأداء مرتين في السنة:
- تقييم نصف السنة: يونيو (تطويري، بدون تقييم رسمي)
- تقييم نهاية السنة: ديسمبر (تقييم رسمي + تعديل الراتب)

### 4.2 مقياس التقييم
1. يحتاج تحسين - أداء أقل من المتوقع، قد يتم وضع خطة تحسين
2. يلبي التوقعات - أداء جيد، زيادة معيارية (3-5%)
3. يتجاوز التوقعات - أداء متميز، زيادة فوق المعيار (6-10%)
4. أداء استثنائي - من أفضل الموظفين، زيادة كبيرة + مضاعف المكافأة (11-18%)
5. أداء تحويلي - نادر، محجوز للإنجازات الاستثنائية (19-25%)

## الفصل الخامس: المكاتب

### مكتب دبي الرئيسي
- العنوان: برج المستقبل، شارع الشيخ زايد، دبي
- السعة: 180 موظف
- المرافق: كافتيريا، صالة رياضية، غرفة صلاة، حضانة أطفال

### مكتب أبوظبي
- العنوان: جزيرة المارية، أبوظبي
- السعة: 50 موظف
- التركيز: العمليات الحكومية والقطاع المصرفي

### مكتب الرياض
- العنوان: حي العليا، طريق الملك فهد، الرياض
- السعة: 30 موظف
- التركيز: التوسع في السوق السعودي

## الملحق: جهات الاتصال
| القسم | المسؤول | البريد الإلكتروني | الهاتف |
|-------|---------|-----------------|--------|
| الموارد البشرية | نورة الكعبي | hr@ruyatech.ae | 04-555-0201 |
| تقنية المعلومات | خالد العامري | it@ruyatech.ae | 04-555-0202 |
| المالية | سارة المهيري | finance@ruyatech.ae | 04-555-0203 |
| القانونية | عمر الشامسي | legal@ruyatech.ae | 04-555-0204 |
| الإدارة | مريم الفلاسي | admin@ruyatech.ae | 04-555-0205 |

آخر تحديث: 15 يناير 2025
الإصدار: 2.1
"""

with open('/tmp/test_handbook_ar.txt', 'w', encoding='utf-8') as f:
    f.write(ar_medium)
print(f"Medium Arabic doc: {len(ar_medium):,} chars")


# ============================================================
# 3. LARGE English doc (~65K chars) - Forces RAG + Reranker
# ============================================================
departments = [
    ('Engineering', 'software development, DevOps, QA, and platform engineering'),
    ('Data Science', 'machine learning, analytics, data engineering, and research'),
    ('Product', 'product management, UX design, and user research'),
    ('Sales', 'enterprise sales, SMB sales, partnerships, and business development'),
    ('Marketing', 'content, demand generation, brand, and events'),
    ('Finance', 'accounting, FP&A, treasury, and procurement'),
    ('HR', 'talent acquisition, people operations, L&D, and compensation'),
    ('Legal', 'contracts, compliance, IP, and regulatory affairs'),
    ('Operations', 'IT, facilities, supply chain, and vendor management'),
    ('Customer Success', 'onboarding, support, renewals, and expansion'),
]

employees = [
    ('John Smith', 'Senior Specialist', 155000, 'Exceeds', 'Project Atlas, Infra Migration'),
    ('Emily Johnson', 'Staff Specialist', 195000, 'Outstanding', 'Project Neptune, API Redesign'),
    ('Michael Brown', 'Junior Specialist', 82000, 'Meets', 'Bug Fixes, Documentation'),
    ('Sarah Davis', 'Mid-Level Specialist', 118000, 'Exceeds', 'Feature Development, Testing'),
    ('Robert Wilson', 'Principal Specialist', 245000, 'Exceptional', 'Architecture Review, Mentorship'),
    ('Jennifer Martinez', 'Senior Specialist', 162000, 'Meets', 'Security Audit, Compliance'),
    ('David Anderson', 'Mid-Level Specialist', 125000, 'Exceeds', 'Data Pipeline, ETL'),
    ('Lisa Thomas', 'Staff Specialist', 202000, 'Outstanding', 'ML Infrastructure, Model Serving'),
    ('James Taylor', 'Junior Specialist', 78000, 'Meets', 'Frontend Development, UI Tests'),
    ('Maria Garcia', 'Senior Specialist', 170000, 'Exceeds', 'Mobile App, Cross-Platform'),
    ('William Lee', 'Distinguished Specialist', 310000, 'Exceptional', 'System Architecture, Patents'),
    ('Patricia White', 'Mid-Level Specialist', 115000, 'Meets', 'Integration Testing, CI/CD'),
]

parts = []
parts.append("# Global TechCorp - Annual Company Report 2024\n\n")
parts.append("## Executive Summary\n")
parts.append("Global TechCorp reported record revenue of $2.3 billion in fiscal year 2024, ")
parts.append("representing a 28% increase over the previous year. The company expanded to ")
parts.append("4,200 employees across 15 offices worldwide. Key achievements include the ")
parts.append("launch of our AI-powered analytics platform (Project Quantum), securing 45 ")
parts.append("enterprise contracts worth over $1M each, and achieving SOC 2 Type II and ")
parts.append("ISO 27001 certifications.\n\n")

for dept_name, dept_desc in departments:
    parts.append(f"## Department: {dept_name}\n")
    parts.append(f"Focus areas: {dept_desc}\n\n")
    parts.append(f"### {dept_name} - Team Roster & Performance\n\n")
    parts.append("| Employee | Title | Base Salary | Rating | Key Projects |\n")
    parts.append("|----------|-------|-------------|--------|-------------|\n")
    for name, title, salary, perf, projects in employees:
        parts.append(f"| {name} | {title} | ${salary:,} | {perf} | {projects} |\n")

    parts.append(f"\n### {dept_name} - Quarterly Metrics\n\n")
    parts.append("| Quarter | Revenue Impact | Projects Completed | Customer Satisfaction | Team Growth |\n")
    parts.append("|---------|---------------|-------------------|---------------------|------------|\n")
    parts.append("| Q1 2024 | $12.5M | 8 | 4.2/5.0 | +5 hires |\n")
    parts.append("| Q2 2024 | $15.8M | 12 | 4.5/5.0 | +8 hires |\n")
    parts.append("| Q3 2024 | $18.2M | 15 | 4.6/5.0 | +3 hires |\n")
    parts.append("| Q4 2024 | $22.1M | 18 | 4.8/5.0 | +6 hires |\n\n")

    parts.append(f"### {dept_name} - Budget Allocation 2024\n")
    parts.append("- Personnel costs: $8.5M (65% of department budget)\n")
    parts.append("- Tools & Software: $1.2M (9%)\n")
    parts.append("- Training & Development: $650K (5%)\n")
    parts.append("- Travel & Conferences: $420K (3%)\n")
    parts.append("- Infrastructure: $2.3M (18%)\n\n")

    parts.append(f"### {dept_name} - Goals for 2025\n")
    parts.append("1. Increase team productivity by 15% through automation\n")
    parts.append("2. Achieve 95% employee retention rate\n")
    parts.append(f"3. Launch 3 new {dept_name.lower()}-related initiatives\n")
    parts.append("4. Reduce operational costs by 10%\n")
    parts.append("5. Improve cross-department collaboration score to 4.5/5.0\n\n")

    parts.append(f"### {dept_name} - Risk Assessment\n")
    parts.append(f"Key risks identified for the {dept_name} department:\n")
    parts.append("- Talent retention in competitive market (HIGH)\n")
    parts.append("- Technology debt accumulation (MEDIUM)\n")
    parts.append("- Regulatory compliance changes (MEDIUM)\n")
    parts.append("- Budget constraints due to expansion (LOW)\n\n")
    parts.append("---\n\n")

large_en = "".join(parts)
with open('/tmp/test_large_report_en.txt', 'w', encoding='utf-8') as f:
    f.write(large_en)
print(f"Large English doc: {len(large_en):,} chars")


# ============================================================
# 4. LARGE Arabic doc (~60K chars) - Forces RAG + Reranker
# ============================================================
ar_departments = [
    ('الهندسة', 'تطوير البرمجيات وعمليات التطوير وضمان الجودة وهندسة المنصات'),
    ('علوم البيانات', 'التعلم الآلي والتحليلات وهندسة البيانات والأبحاث'),
    ('المنتجات', 'إدارة المنتجات وتصميم تجربة المستخدم وأبحاث المستخدمين'),
    ('المبيعات', 'مبيعات المؤسسات والشركات الصغيرة والشراكات وتطوير الأعمال'),
    ('التسويق', 'المحتوى وتوليد الطلب والعلامة التجارية والفعاليات'),
    ('المالية', 'المحاسبة والتخطيط المالي والخزينة والمشتريات'),
    ('الموارد البشرية', 'استقطاب المواهب وعمليات الأفراد والتطوير والتعويضات'),
    ('الشؤون القانونية', 'العقود والامتثال والملكية الفكرية والشؤون التنظيمية'),
    ('العمليات', 'تقنية المعلومات والمرافق وسلسلة التوريد وإدارة الموردين'),
    ('نجاح العملاء', 'التأهيل والدعم والتجديدات والتوسع'),
]

ar_employees = [
    ('أحمد محمد الراشدي', 'أخصائي أول', 45000, 'يتجاوز التوقعات', 'مشروع أطلس، ترحيل البنية التحتية'),
    ('فاطمة سعيد المنصوري', 'أخصائية رئيسية', 58000, 'أداء استثنائي', 'مشروع نبتون، إعادة تصميم API'),
    ('خالد عبدالله العامري', 'أخصائي مبتدئ', 15000, 'يلبي التوقعات', 'إصلاح الأخطاء، التوثيق'),
    ('نورة حسن الكعبي', 'أخصائية متوسطة', 28000, 'يتجاوز التوقعات', 'تطوير الميزات، الاختبار'),
    ('عمر يوسف الشامسي', 'أخصائي متميز', 85000, 'أداء تحويلي', 'مراجعة البنية، الإرشاد'),
    ('مريم علي الفلاسي', 'أخصائية أولى', 42000, 'يلبي التوقعات', 'تدقيق الأمان، الامتثال'),
    ('سعيد راشد المهيري', 'أخصائي متوسط', 30000, 'يتجاوز التوقعات', 'خط أنابيب البيانات، ETL'),
    ('سارة خالد البلوشي', 'أخصائية رئيسية', 62000, 'أداء استثنائي', 'بنية ML، خدمة النماذج'),
    ('محمد أحمد الظاهري', 'أخصائي مبتدئ', 14000, 'يلبي التوقعات', 'تطوير الواجهة، اختبارات UI'),
    ('هند سالم الكتبي', 'أخصائية أولى', 48000, 'يتجاوز التوقعات', 'تطبيق الهاتف، عبر المنصات'),
    ('عبدالرحمن محمد النعيمي', 'أخصائي متميز', 95000, 'أداء تحويلي', 'بنية النظام، براءات الاختراع'),
    ('لطيفة أحمد الحمادي', 'أخصائية متوسطة', 26000, 'يلبي التوقعات', 'اختبار التكامل، CI/CD'),
]

ar_parts = []
ar_parts.append("# شركة التقنية العالمية - التقرير السنوي 2024\n\n")
ar_parts.append("## الملخص التنفيذي\n")
ar_parts.append("سجلت شركة التقنية العالمية إيرادات قياسية بلغت 8.5 مليار درهم في السنة المالية 2024، ")
ar_parts.append("بزيادة قدرها 28% عن العام السابق. توسعت الشركة لتضم 4,200 موظف في 15 مكتباً حول العالم. ")
ar_parts.append("تشمل الإنجازات الرئيسية إطلاق منصة التحليلات المدعومة بالذكاء الاصطناعي (مشروع كوانتم)، ")
ar_parts.append("وتأمين 45 عقداً مؤسسياً بقيمة تزيد عن 3.7 مليون درهم لكل عقد.\n\n")

for dept_name, dept_desc in ar_departments:
    ar_parts.append(f"## قسم: {dept_name}\n")
    ar_parts.append(f"مجالات التركيز: {dept_desc}\n\n")
    ar_parts.append(f"### {dept_name} - قائمة الفريق والأداء\n\n")
    ar_parts.append("| الموظف | المسمى الوظيفي | الراتب الأساسي | التقييم | المشاريع الرئيسية |\n")
    ar_parts.append("|--------|---------------|--------------|--------|------------------|\n")
    for name, title, salary, perf, projects in ar_employees:
        ar_parts.append(f"| {name} | {title} | {salary:,} درهم | {perf} | {projects} |\n")

    ar_parts.append(f"\n### {dept_name} - المقاييس الفصلية\n\n")
    ar_parts.append("| الربع | تأثير الإيرادات | المشاريع المنجزة | رضا العملاء | نمو الفريق |\n")
    ar_parts.append("|-------|---------------|----------------|------------|------------|\n")
    ar_parts.append("| الربع الأول 2024 | 46 مليون درهم | 8 | 4.2/5.0 | +5 توظيف |\n")
    ar_parts.append("| الربع الثاني 2024 | 58 مليون درهم | 12 | 4.5/5.0 | +8 توظيف |\n")
    ar_parts.append("| الربع الثالث 2024 | 67 مليون درهم | 15 | 4.6/5.0 | +3 توظيف |\n")
    ar_parts.append("| الربع الرابع 2024 | 81 مليون درهم | 18 | 4.8/5.0 | +6 توظيف |\n\n")

    ar_parts.append(f"### {dept_name} - توزيع الميزانية 2024\n")
    ar_parts.append("- تكاليف الموظفين: 31 مليون درهم (65% من ميزانية القسم)\n")
    ar_parts.append("- الأدوات والبرمجيات: 4.4 مليون درهم (9%)\n")
    ar_parts.append("- التدريب والتطوير: 2.4 مليون درهم (5%)\n")
    ar_parts.append("- السفر والمؤتمرات: 1.5 مليون درهم (3%)\n")
    ar_parts.append("- البنية التحتية: 8.5 مليون درهم (18%)\n\n")

    ar_parts.append(f"### {dept_name} - أهداف 2025\n")
    ar_parts.append("1. زيادة إنتاجية الفريق بنسبة 15% من خلال الأتمتة\n")
    ar_parts.append("2. تحقيق معدل استبقاء موظفين 95%\n")
    ar_parts.append(f"3. إطلاق 3 مبادرات جديدة متعلقة بـ{dept_name}\n")
    ar_parts.append("4. خفض التكاليف التشغيلية بنسبة 10%\n")
    ar_parts.append("5. تحسين درجة التعاون بين الأقسام إلى 4.5/5.0\n\n")

    ar_parts.append(f"### {dept_name} - تقييم المخاطر\n")
    ar_parts.append(f"المخاطر الرئيسية المحددة لقسم {dept_name}:\n")
    ar_parts.append("- استبقاء المواهب في سوق تنافسي (عالي)\n")
    ar_parts.append("- تراكم الديون التقنية (متوسط)\n")
    ar_parts.append("- تغييرات الامتثال التنظيمي (متوسط)\n")
    ar_parts.append("- قيود الميزانية بسبب التوسع (منخفض)\n\n")
    ar_parts.append("---\n\n")

large_ar = "".join(ar_parts)
with open('/tmp/test_large_report_ar.txt', 'w', encoding='utf-8') as f:
    f.write(large_ar)
print(f"Large Arabic doc: {len(large_ar):,} chars")

print("\nAll 4 test files created!")
