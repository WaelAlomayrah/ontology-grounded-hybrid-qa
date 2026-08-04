import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Language = 'en' | 'ar';

const ar: Record<string, string> = {
  'Ontology Studio': 'استوديو الأنطولوجيا',
  'Explainable knowledge intelligence': 'ذكاء معرفي قابل للتفسير',
  Chat: 'المحادثة',
  Graph: 'الرسم المعرفي',
  Operations: 'العمليات',
  Modeling: 'النمذجة',
  Evaluation: 'التقييم',
  'First-run guide': 'دليل البدء',
  'Build knowledge without technical modeling': 'ابنِ المعرفة دون نمذجة تقنية',
  'Add a CSV file': 'أضف ملف CSV',
  'Check the sample rows': 'تحقق من الصفوف النموذجية',
  'Say what one row represents': 'حدد ما يمثله الصف الواحد',
  'Describe each useful column': 'صف كل عمود مفيد',
  'Check and save your work': 'تحقق من عملك واحفظه',
  'Ask an administrator to publish': 'اطلب من المسؤول النشر',
  'Open guided modeling →': 'افتح النمذجة الموجّهة ←',
  'Close guide': 'إغلاق الدليل',
  'Welcome back': 'مرحبًا بعودتك',
  'Sign in to explore data, describe knowledge, and ask evidence-grounded questions.': 'سجّل الدخول لاستكشاف البيانات ووصف المعرفة وطرح أسئلة مدعومة بالأدلة.',
  Username: 'اسم المستخدم',
  Password: 'كلمة المرور',
  'Signing in…': 'جارٍ تسجيل الدخول…',
  'Sign in': 'تسجيل الدخول',
  'Use your assigned viewer, labeler, analyst, or administrator account.': 'استخدم حساب المشاهد أو المصنّف أو المحلل أو المسؤول المخصص لك.',
  'New conversation': 'محادثة جديدة',
  'Saved investigations': 'المحادثات المحفوظة',
  Rename: 'إعادة التسمية',
  Delete: 'حذف',
  'Conversation name': 'اسم المحادثة',
  'New investigation': 'استكشاف جديد',
  'Knowledge workspace': 'مساحة المعرفة',
  'loading dataset': 'جارٍ تحميل مجموعة البيانات',
  'Ask, investigate, continue.': 'اسأل، استكشف، وتابع.',
  'Every response stays in context visually, with its evidence and ontology path close at hand.': 'تبقى كل إجابة ضمن سياق مرئي مع أدلتها ومسار الأنطولوجيا.',
  'Retrieval mode': 'وضع الاسترجاع',
  hybrid: 'هجين',
  'graph only': 'الرسم فقط',
  'vector only': 'المتجهات فقط',
  'Start with a question about your data': 'ابدأ بسؤال عن بياناتك',
  'I’ll combine semantic retrieval with explicit graph relationships and show you why the answer is supported.': 'سأجمع الاسترجاع الدلالي مع علاقات الرسم الصريحة وأوضح سبب دعم الإجابة.',
  You: 'أنت',
  'Traversing the graph and ranking evidence…': 'جارٍ تتبع الرسم وترتيب الأدلة…',
  'Ask a follow-up question…': 'اطرح سؤال متابعة…',
  'Ask the knowledge graph…': 'اسأل الرسم المعرفي…',
  '↵ send · shift + ↵ new line': '↵ إرسال · Shift + ↵ سطر جديد',
  Ask: 'اسأل',
  'Ontology assistant': 'مساعد الأنطولوجيا',
  'Grounded response': 'إجابة مدعومة',
  answered: 'تمت الإجابة',
  partial: 'إجابة جزئية',
  'insufficient evidence': 'أدلة غير كافية',
  Confidence: 'الثقة',
  'Graph facts': 'حقائق الرسم',
  Entities: 'الكيانات',
  Latency: 'زمن الاستجابة',
  'Inspect supporting evidence': 'فحص الأدلة الداعمة',
  'Running baseline comparison…': 'جارٍ تشغيل مقارنة خط الأساس…',
  'Open supporting graph': 'فتح الرسم الداعم',
  'Compare retrieval': 'مقارنة الاسترجاع',
  'Sources:': 'المصادر:',
  none: 'لا يوجد',

  'Visual investigation': 'استكشاف مرئي',
  'Knowledge graph': 'الرسم المعرفي',
  'Follow relationships, distinguish entity classes, and inspect the ontology that gives the data meaning.': 'تتبّع العلاقات، وميّز فئات الكيانات، وافحص الأنطولوجيا التي تمنح البيانات معناها.',
  triples: 'ثلاثيات',
  resources: 'موارد',
  'Instance graph': 'رسم المثيلات',
  'Ontology layer': 'طبقة الأنطولوجيا',
  'Answer evidence path': 'مسار دليل الإجابة',
  'Restore highlighted path': 'استعادة المسار المميز',
  'Find an entity…': 'ابحث عن كيان…',
  Explore: 'استكشف',
  Depth: 'العمق',
  '1 hop': 'خطوة واحدة',
  '2 hops': 'خطوتان',
  '3 hops': '3 خطوات',
  Direction: 'الاتجاه',
  Outgoing: 'صادر',
  Incoming: 'وارد',
  Both: 'كلاهما',
  Relation: 'العلاقة',
  All: 'الكل',
  Spread: 'انتشار',
  Circle: 'دائرة',
  Grid: 'شبكة',
  'Spread relationship layout': 'توزيع العلاقات',
  'Arrange in a circle': 'ترتيب دائري',
  'Arrange in a grid': 'ترتيب شبكي',
  'Pin or unpin selected node': 'تثبيت العقدة المحددة أو إلغاء تثبيتها',
  'Undo last expansion': 'التراجع عن آخر توسع',
  'Fit graph': 'ملاءمة الرسم',
  'Reset graph': 'إعادة ضبط الرسم',
  Object: 'كائن',
  Relationship: 'علاقة',
  Identifier: 'المعرّف',
  From: 'من',
  To: 'إلى',
  'Source ID': 'معرّف المصدر',
  'Target ID': 'معرّف الهدف',
  Inspector: 'الفاحص',
  'Expand neighbors →': 'توسيع الجيران ←',
  'Select a node': 'حدد عقدة',
  'Click any colored node to inspect its class, identifier, and properties.': 'انقر أي عقدة ملوّنة لفحص فئتها ومعرّفها وخصائصها.',
  'Ontology vocabulary': 'مفردات الأنطولوجيا',
  classes: 'فئات',
  'declared properties': 'خصائص معرّفة',

  'Live operations': 'العمليات المباشرة',
  'System observability': 'مراقبة النظام',
  'Health, container load, ingestion state, and available research datasets in one view.': 'الصحة وحمل الحاويات وحالة الإدخال ومجموعات البيانات البحثية في شاشة واحدة.',
  'Open Grafana ↗': 'فتح Grafana ↗',
  'Platform status': 'حالة المنصة',
  Checking: 'جارٍ التحقق',
  'Core retrieval services': 'خدمات الاسترجاع الأساسية',
  'Active containers': 'الحاويات النشطة',
  'Reported by Docker Engine': 'وفقًا لمحرك Docker',
  'Indexed vectors': 'المتجهات المفهرسة',
  'Milvus collection': 'مجموعة Milvus',
  'Datasets found': 'مجموعات البيانات الموجودة',
  'Mounted under /data': 'محمّلة ضمن ‎/data',
  'Active workspace': 'مساحة العمل النشطة',
  'Latest ingestion': 'آخر إدخال',
  'No report since restart': 'لا يوجد تقرير منذ إعادة التشغيل',
  'Persisted vectors remain available in Milvus.': 'المتجهات المحفوظة ما زالت متاحة في Milvus.',
  'Container status & load': 'حالة الحاويات والحمل',
  Live: 'مباشر',
  'Prometheus metrics are temporarily unavailable.': 'مقاييس Prometheus غير متاحة مؤقتًا.',
  'Service targets': 'أهداف الخدمات',
  'Application checks and Prometheus scrape state.': 'فحوص التطبيق وحالة جمع Prometheus.',
  'Healthy and responding': 'سليمة وتستجيب',
  Unavailable: 'غير متاحة',
  Online: 'متصل',
  Offline: 'غير متصل',
  Scraping: 'جارٍ الجمع',
  Down: 'متوقف',
  'Available datasets': 'مجموعات البيانات المتاحة',
  'Download a complete, self-contained ZIP without changing source files.': 'نزّل ملف ZIP كاملًا ومستقلًا دون تغيير ملفات المصدر.',
  'ingestion ready': 'جاهزة للإدخال',
  'source available': 'المصدر متاح',
  'Preparing…': 'جارٍ التحضير…',
  'Export ZIP': 'تصدير ZIP',
  CPU: 'المعالج',
  Memory: 'الذاكرة',
  'Network ↓': 'الشبكة ↓',
  'Network ↑': 'الشبكة ↑',

  'Guided knowledge modeling': 'نمذجة معرفية موجّهة',
  'Build a knowledge model': 'بناء نموذج معرفي',
  'No ontology or coding experience is needed. Describe what each row and column means in everyday language.': 'لا تحتاج إلى خبرة في الأنطولوجيا أو البرمجة. صف معنى كل صف وعمود بلغة بسيطة.',
  'Published graph': 'الرسم المنشور',
  checking: 'جارٍ التحقق',
  '1. Add data': '1. إضافة البيانات',
  '2. Describe data': '2. وصف البيانات',
  '3. Review ontology': '3. مراجعة الأنطولوجيا',
  'Labeler guide': 'دليل مصنّف البيانات',
  'Describe your file': 'صف ملفك',
  'Tell the system what one row represents, then give every useful column a meaning.': 'أخبر النظام بما يمثله الصف الواحد، ثم حدد معنى كل عمود مفيد.',
  'File or dataset': 'الملف أو مجموعة البيانات',
  'Complete Arabic dataset detected.': 'تم اكتشاف مجموعة البيانات العربية الكاملة.',
  'Its validated RDF graph, 3,000 Arabic documents, ontology, and 400 evaluation questions will be ingested together. CSV mapping is not required for this prepared dataset.': 'سيتم إدخال رسم RDF المعتمد و3,000 مستند عربي والأنطولوجيا و400 سؤال تقييم معًا. لا يلزم تعيين CSV لهذه المجموعة الجاهزة.',
  'Start with a list of things.': 'ابدأ بقائمة من الأشياء.',
  'For example, upload customers and products before uploading a file that connects customers to orders. Use the same IDs in every file.': 'ارفع العملاء والمنتجات قبل ملف يربط العملاء بالطلبات، واستخدم المعرّفات نفسها في كل ملف.',
  'file objects': 'كائنات ملفات',
  ready: 'جاهز',
  'choices left': 'خيارات متبقية',
  'Check and save': 'تحقق واحفظ',
  'Your account is read-only. Ask for a labeler account to describe data.': 'حسابك للقراءة فقط. اطلب حساب مصنّف لوصف البيانات.',
  'Action failed': 'فشل الإجراء',
  'Please fix these choices': 'يرجى تصحيح هذه الاختيارات',
  'Data source': 'مصدر البيانات',
  'One row is': 'الصف الواحد يمثل',
  'Not named yet': 'لم تتم تسميته',
  Ready: 'جاهز',
  'What does one row represent?': 'ماذا يمثل الصف الواحد؟',
  'Example: Customer': 'مثال: عميل',
  'Example: works for': 'مثال: يعمل لدى',
  'What kind of file is this?': 'ما نوع هذا الملف؟',
  'A list of things': 'قائمة أشياء',
  'People, products, orders, places…': 'أشخاص، منتجات، طلبات، أماكن…',
  'Connections between things': 'روابط بين الأشياء',
  'Employee works for department': 'موظف يعمل لدى إدارة',
  'To make this ready:': 'لجعله جاهزًا:',
  'Column in your file': 'العمود في ملفك',
  'What does it mean?': 'ماذا يعني؟',
  'Name in the model': 'الاسم في النموذج',
  'Unique ID': 'معرّف فريد',
  'Display name': 'اسم العرض',
  Detail: 'تفصيل',
  'From item': 'من العنصر',
  'To item': 'إلى العنصر',
  'Connection name': 'اسم العلاقة',
  'Do not import': 'عدم الاستيراد',
  'No description is available': 'لا يوجد وصف متاح',
  'Go to “Add data” and upload a CSV file first.': 'انتقل إلى «إضافة البيانات» وارفع ملف CSV أولًا.',
  'Ingestion configuration': 'إعدادات الإدخال',
  'Choose how this dataset is indexed': 'اختر كيفية فهرسة مجموعة البيانات',
  'Indexes are isolated by dataset and embedding model, so experiments cannot overwrite each other.': 'الفهارس معزولة حسب مجموعة البيانات ونموذج التضمين، فلا تستبدل التجارب بعضها.',
  Operation: 'العملية',
  'Embedding model': 'نموذج التضمين',
  Processor: 'المعالج',
  'Embedding batch': 'دفعة التضمين',
  'Save reusable vectors': 'حفظ متجهات قابلة لإعادة الاستخدام',
  'Include validated precomputed vectors in future dataset exports.': 'تضمين المتجهات المحسوبة مسبقًا والمعتمدة في عمليات التصدير المستقبلية.',
  'Add to the graph': 'إضافة إلى الرسم',
  'Replace the graph': 'استبدال الرسم',
  'Publish selected configuration': 'نشر الإعداد المحدد',
  'Only new or changed searchable text will be embedded.': 'سيتم تضمين النص الجديد أو المتغير فقط.',
  'The graph and selected model index will be rebuilt.': 'سيُعاد بناء الرسم وفهرس النموذج المحدد.',
  'Only the selected storage layer will be updated.': 'سيتم تحديث طبقة التخزين المحددة فقط.',
  'Target index': 'الفهرس المستهدف',
  'Run Arabic dataset ingestion': 'تشغيل إدخال البيانات العربية',
  'Build knowledge graph': 'بناء الرسم المعرفي',
  'Knowledge graph built': 'تم بناء الرسم المعرفي',
  'Build failed': 'فشل البناء',
  'Why it failed': 'سبب الفشل',
  'Step 1': 'الخطوة 1',
  'Add a spreadsheet saved as CSV': 'إضافة جدول بيانات محفوظ بصيغة CSV',
  'We inspect the headings and show a preview. Nothing is published yet.': 'نفحص العناوين ونعرض معاينة. لن يُنشر شيء بعد.',
  '+ Choose CSV file': '+ اختر ملف CSV',
  'Reading headings and sample rows…': 'جارٍ قراءة العناوين والصفوف النموذجية…',
  'No files added yet': 'لم تتم إضافة ملفات',
  'Choose a CSV file to begin.': 'اختر ملف CSV للبدء.',
  'File checked': 'تم فحص الملف',
  'Describe this data →': 'صف هذه البيانات ←',
  'Does this preview look correct?': 'هل تبدو هذه المعاينة صحيحة؟',
  'Select a file': 'حدد ملفًا',
  'You will see its headings and first few rows here before describing it.': 'سترى عناوينه وصفوفه الأولى هنا قبل وصفه.',
  'Types of things': 'أنواع الأشياء',
  types: 'أنواع',
  'Find a type…': 'ابحث عن نوع…',
  'top-level type': 'نوع رئيسي',
  'Selected type': 'النوع المحدد',
  'Show items and connections →': 'عرض العناصر والروابط ←',
  Items: 'العناصر',
  'Belongs under': 'ينتمي تحت',
  None: 'لا يوجد',
  'Connected details': 'التفاصيل المرتبطة',
  'Details and connections': 'التفاصيل والروابط',
  Name: 'الاسم',
  Kind: 'النوع',
  'Used by': 'يُستخدم بواسطة',
  'Points to': 'يشير إلى',
  'No ontology types yet': 'لا توجد أنواع أنطولوجيا بعد',
  'Add and publish a file to create the first type.': 'أضف ملفًا وانشره لإنشاء النوع الأول.',
  'Data labeler guide': 'دليل مصنّف البيانات',
  'Turn rows into understandable knowledge': 'حوّل الصفوف إلى معرفة مفهومة',
  'Your job is to explain what the data means. The system handles the technical graph format.': 'مهمتك شرح معنى البيانات، ويتولى النظام الصيغة التقنية للرسم.',
  'Prepare the file': 'إعداد الملف',
  'Add and preview': 'الإضافة والمعاينة',
  'Describe one row': 'وصف صف واحد',
  'Describe columns': 'وصف الأعمدة',
  'Example: a list of things': 'مثال: قائمة أشياء',
  'Example: connections': 'مثال: روابط',
  'CSV column': 'عمود CSV',
  Meaning: 'المعنى',
  'Quality checklist': 'قائمة فحص الجودة',
  'When to ask for help': 'متى تطلب المساعدة',
  'Remember:': 'تذكّر:',

  'Quality lab': 'مختبر الجودة',
  'Retrieval evaluation': 'تقييم الاسترجاع',
  'Choose an indexed dataset and embedding model, then compare graph, vector, hybrid, and ontology grounding.': 'اختر مجموعة بيانات مفهرسة ونموذج تضمين، ثم قارن الرسم والمتجهات والهجين والتأصيل الأنطولوجي.',
  Dataset: 'مجموعة البيانات',
  starting: 'بدء التشغيل',
  'Index ready for evaluation': 'الفهرس جاهز للتقييم',
  'Ingest this dataset/model combination first': 'أدخل مجموعة البيانات ونموذجها أولًا',
  'Run evaluation': 'تشغيل التقييم',
  'Export JSON': 'تصدير JSON',
  'Evaluation failed': 'فشل التقييم',
  'No evaluation results yet': 'لا توجد نتائج تقييم بعد',
  'Run the benchmark to generate the dashboard.': 'شغّل الاختبار المعياري لإنشاء لوحة المعلومات.',
  'Primary analysis': 'التحليل الأساسي',
  'What does the ontology improve?': 'ما الذي تحسّنه الأنطولوجيا؟',
  'Controlled comparison across accuracy, evidence quality, and response cost.': 'مقارنة مضبوطة للدقة وجودة الأدلة وتكلفة الاستجابة.',
  'Overall quality impact': 'الأثر الإجمالي على الجودة',
  'improvement with ontology': 'تحسن مع الأنطولوجيا',
  'decrease with ontology': 'انخفاض مع الأنطولوجيا',
  'Evaluation ground': 'محور التقييم',
  'Without ontology': 'دون أنطولوجيا',
  'With ontology': 'مع الأنطولوجيا',
  Impact: 'الأثر',
  'Answer accuracy': 'دقة الإجابة',
  'Expected answer keyword coverage': 'تغطية كلمات الإجابة المتوقعة',
  'Evidence accuracy': 'دقة الأدلة',
  'Entity and relationship evidence recall': 'استدعاء أدلة الكيانات والعلاقات',
  'Entity recall': 'استدعاء الكيانات',
  'Expected entities retrieved': 'الكيانات المتوقعة المسترجعة',
  'Relationship grounding': 'تأصيل العلاقات',
  'Expected graph paths recovered': 'مسارات الرسم المتوقعة المستعادة',
  'Answer reliability': 'موثوقية الإجابة',
  'Questions completed with an answered status': 'الأسئلة المكتملة بحالة تمت الإجابة',
  'Average end-to-end retrieval time': 'متوسط زمن الاسترجاع من البداية إلى النهاية',
  'Supporting retrieval detail': 'تفاصيل الاسترجاع الداعمة',
  'Individual mode scores behind the ontology impact analysis.': 'درجات الأوضاع التي يستند إليها تحليل أثر الأنطولوجيا.',
  Vector: 'المتجهات',
  Hybrid: 'الهجين',
  'Structured facts and paths': 'حقائق ومسارات منظمة',
  'Semantic similarity': 'تشابه دلالي',
  'Graph + semantic evidence': 'أدلة الرسم والدلالة',
  'Ontology grounding': 'التأصيل الأنطولوجي',
  'Typed entities + relation grounding': 'كيانات مصنفة وتأصيل علاقات',
  'Quality by metric': 'الجودة حسب المقياس',
  'Higher is better': 'الأعلى أفضل',
  'Answer coverage': 'تغطية الإجابة',
  'Path recall': 'استدعاء المسار',
  'Typed entities': 'الكيانات المصنفة',
  'Speed and reliability': 'السرعة والموثوقية',
  'Latency and completed answers': 'زمن الاستجابة والإجابات المكتملة',
  'Graph activation': 'تفعيل الرسم',
  'Typed graph coverage': 'تغطية الرسم المصنف',
  'Question-level comparison': 'مقارنة على مستوى السؤال',
  'Overall quality score for each benchmark question': 'درجة الجودة الإجمالية لكل سؤال معياري',
  Question: 'السؤال',
  Best: 'الأفضل',
};

const en = Object.fromEntries(Object.entries(ar).map(([english, arabic]) => [arabic, english]));
const skipSelector = '.answer-text,.user-message,.entity-chips,pre,code,.graph,.comparison,[data-i18n-skip]';

function dynamic(value: string, language: Language): string {
  if (language === 'ar') {
    return value
      .replace(/^(\d+) questions$/, '$1 سؤالًا')
      .replace(/^Dataset: (.+)$/, 'مجموعة البيانات: $1')
      .replace(/^Model: (.+)$/, 'النموذج: $1')
      .replace(/^Last run (.+)$/, 'آخر تشغيل $1')
      .replace(/^Best overall: (.+)$/, 'الأفضل إجمالًا: $1')
      .replace(/^(\d+) nodes · (\d+) relationships$/, '$1 عقدة · $2 علاقة')
      .replace(/^(\d+) traversed relationships are highlighted; unrelated context is dimmed\.$/, 'تم تمييز $1 من العلاقات المتتبعة وتعتيم السياق غير المرتبط.')
      .replace(/^(\d+) rows · (\d+) columns$/, '$1 صف · $2 عمود')
      .replace(/^We found ([\d,]+) rows and (\d+) columns\.$/, 'وجدنا $1 صفًا و$2 عمودًا.')
      .replace(/^(\d+) files · (\d+) data tables\/resources$/, '$1 ملف · $2 جدول/مورد بيانات')
      .replace(/^(\d+) ms average$/, 'متوسط $1 مللي ثانية')
      .replace(/^(\d+)% answered$/, 'تمت الإجابة عن $1%')
      .replace(/^Graph only · (.+)$/, 'الرسم فقط · $1')
      .replace(/^Vector only · (.+)$/, 'المتجهات فقط · $1')
      .replace(/^Sources: (.+)$/, 'المصادر: $1');
  }
  return value
    .replace(/^(\d+) سؤالًا$/, '$1 questions')
    .replace(/^مجموعة البيانات: (.+)$/, 'Dataset: $1')
    .replace(/^النموذج: (.+)$/, 'Model: $1')
    .replace(/^آخر تشغيل (.+)$/, 'Last run $1')
    .replace(/^الأفضل إجمالًا: (.+)$/, 'Best overall: $1')
    .replace(/^(\d+) عقدة · (\d+) علاقة$/, '$1 nodes · $2 relationships')
    .replace(/^تم تمييز (\d+) من العلاقات المتتبعة وتعتيم السياق غير المرتبط\.$/, '$1 traversed relationships are highlighted; unrelated context is dimmed.')
    .replace(/^(\d+) صف · (\d+) عمود$/, '$1 rows · $2 columns')
    .replace(/^وجدنا ([\d,]+) صفًا و(\d+) عمودًا\.$/, 'We found $1 rows and $2 columns.')
    .replace(/^(\d+) ملف · (\d+) جدول\/مورد بيانات$/, '$1 files · $2 data tables/resources')
    .replace(/^متوسط (\d+) مللي ثانية$/, '$1 ms average')
    .replace(/^تمت الإجابة عن (\d+)%$/, '$1% answered')
    .replace(/^الرسم فقط · (.+)$/, 'Graph only · $1')
    .replace(/^المتجهات فقط · (.+)$/, 'Vector only · $1')
    .replace(/^المصادر: (.+)$/, 'Sources: $1');
}

function translate(value: string, language: Language): string {
  const leading = value.match(/^\s*/)?.[0] ?? '';
  const trailing = value.match(/\s*$/)?.[0] ?? '';
  const clean = value.trim();
  if (!clean) return value;
  const result = language === 'ar' ? ar[clean] ?? dynamic(clean, language) : en[clean] ?? dynamic(clean, language);
  return `${leading}${result}${trailing}`;
}

function skipped(element: Element | null): boolean {
  return Boolean(element?.closest(skipSelector));
}

function translateTree(root: Node, language: Language): void {
  if (root.nodeType === Node.TEXT_NODE) {
    if (!skipped(root.parentElement) && root.nodeValue) {
      const result = translate(root.nodeValue, language);
      if (result !== root.nodeValue) root.nodeValue = result;
    }
    return;
  }
  if (!(root instanceof Element) || skipped(root)) return;
  for (const attribute of ['placeholder', 'title', 'aria-label']) {
    const value = root.getAttribute(attribute);
    if (value) {
      const result = translate(value, language);
      if (result !== value) root.setAttribute(attribute, result);
    }
  }
  root.childNodes.forEach(node => translateTree(node, language));
}

type ContextValue = {
  language: Language;
  setLanguage: (language: Language) => void;
  toggleLanguage: () => void;
};
const Context = createContext<ContextValue | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [language, setState] = useState<Language>(() => localStorage.getItem('ontology-language') === 'ar' ? 'ar' : 'en');
  const setLanguage = useCallback((next: Language) => {
    localStorage.setItem('ontology-language', next);
    setState(next);
  }, []);
  const toggleLanguage = useCallback(() => setLanguage(language === 'en' ? 'ar' : 'en'), [language, setLanguage]);
  useEffect(() => {
    document.documentElement.lang = language;
    document.documentElement.dir = language === 'ar' ? 'rtl' : 'ltr';
    translateTree(document.body, language);
    const observer = new MutationObserver(records => records.forEach(record => {
      if (record.type === 'characterData') translateTree(record.target, language);
      record.addedNodes.forEach(node => translateTree(node, language));
      if (record.type === 'attributes') translateTree(record.target, language);
    }));
    observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['placeholder', 'title', 'aria-label'] });
    return () => observer.disconnect();
  }, [language]);
  const value = useMemo(() => ({ language, setLanguage, toggleLanguage }), [language, setLanguage, toggleLanguage]);
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useI18n(): ContextValue {
  const value = useContext(Context);
  if (!value) throw new Error('useI18n must be used inside I18nProvider');
  return value;
}

export function LanguageToggle({ compact = false }: { compact?: boolean }) {
  const { language, toggleLanguage } = useI18n();
  return <button
    type="button"
    className={`language-toggle ${compact ? 'compact' : ''}`}
    onClick={toggleLanguage}
    aria-label={language === 'en' ? 'Switch to Arabic' : 'التبديل إلى الإنجليزية'}
    title={language === 'en' ? 'Switch to Arabic' : 'التبديل إلى الإنجليزية'}
    data-i18n-skip
  >
    <span aria-hidden="true">🌐</span>
    <b>{language === 'en' ? 'العربية' : 'English'}</b>
  </button>;
}
