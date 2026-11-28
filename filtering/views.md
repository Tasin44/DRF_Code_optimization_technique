# 2️⃣ Django REST Framework: Filtering, Searching & Ordering Guide

> **সেটআপ (আগাম প্রস্তুতি):**  
> অ্যাডভান্সড ফিল্টারিংয়ের জন্য `pip install django-filter` ইনস্টল করে `settings.py`-এর `INSTALLED_APPS`-এ `"django_filters"` যোগ করতে হয়। *(তবে `SearchFilter` এবং `OrderingFilter` DRF-এর ভেতরেই বিল্ট-ইন থাকে!)*

---

<br>

# 🟢 EASY

## উদাহরণ ১ (Easy): হাতে লেখা `if` চেইন → `SearchFilter` + `OrderingFilter`

<br>

### ❌ আগে (Bad — হাতে লেখা `if` চেইন)

```python
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = BookSerializer

    def get_queryset(self):
        qs = Book.objects.all()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(title__icontains=search)
        ordering = self.request.query_params.get("ordering")
        if ordering:
            qs = qs.order_by(ordering)     # ❌ যেকোনো ফিল্ড নাম দেওয়া যায়!
        return qs
```

> **কী সমস্যা হচ্ছে?**
> 1. **একই কোড বারবার লেখা (Code Duplication):** প্রতিটি ViewSet-এ (Book, Author, Order) গিয়ে একই `if search:`, `if ordering:` কোড কপি-পেস্ট করতে হয়।
> 2. **সার্ভার ক্র্যাশ (`500 Error`):** কোনো ইউজার যদি ভুল করে বা ইচ্ছে করে URL-এ `?ordering=abcxyz` দেয়, তবে জ্যাঙ্গো `FieldError` থ্রো করে পুরো API ক্র্যাশ (500 Error) করিয়ে দেবে!
> 3. **নিরাপত্তা ঝুঁকি (Security):** ইউজার চাইলে `?ordering=author__user__password` দিয়ে গোপন বা ইনডেক্সবিহীন রিলেশনাল ফিল্ড দিয়ে সর্ট করার চেষ্টা করতে পারে—যাতে ডাটাবেজ হ্যাং হতে পারে বা ডেটা লিক হওয়ার ঝুঁকি তৈরি হয়।

<br>

### ✅ পরে (Good — DRF-এর বিল্ট-ইন `SearchFilter` + `OrderingFilter`)

```python
from rest_framework import filters

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author")
    serializer_class = BookSerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "author__name"]       # ?search=django
    ordering_fields = ["price", "title", "id"]      # শুধু এগুলোতেই sort চলবে
    ordering = ["-id"]                              # ডিফল্ট অর্ডারিং
```

<br>

---

<br>

### 💡 একদম সহজ বাংলায় ব্যাখ্যা (বাস্তব উদাহরণ ও লাইন-বাই-লাইন):

ধরুন আপনার একটি **ই-কমার্স বইয়ের দোকান** (যেমন রকমারি) আছে। কাস্টমার দোকানে এসে দুইটা কাজ করতে চায়:
1. **সার্চ (Search):** সার্চ বক্সে `"django"` লিখে বই খুঁজতে চায়।
2. **সর্ট (Ordering):** বইগুলো *"কম দাম থেকে বেশি দাম"* (`?ordering=price`) বা *"বেশি দাম থেকে কম দাম"* (`?ordering=-price`) সাজিয়ে দেখতে চায়।

আগে আপনি নিজের হাতে `get_queryset()`-এর ভেতর `if` দিয়ে এগুলো করছিলেন, যা ছিল অনিরাপদ ও ঝামেলার। এখন আপনি DRF-এর রেডিমেড ২টা রোবট (**`SearchFilter`** আর **`OrderingFilter`**) বসিয়ে দিলেন!

#### প্রতিটি লাইনের কাজ দেখুন:

1. **`filter_backends = [filters.SearchFilter, filters.OrderingFilter]`**
   * এর মানে হলো: এই ViewSet-এ DRF-এর **সার্চ** এবং **সর্টিং**—দুটো ফিচারই চালু করে দাও!

2. **`search_fields = ["title", "author__name"]`**
   * এখানে আপনি বলে দিচ্ছেন: ইউজার `?search=django` লিখলে DRF যেন বইয়ের **`title`** এবং লেখকের **`name` (`author__name`)**—দুটোর ভেতরেই `"django"` শব্দটা খোঁজে!
   * **ডাটাবেজে কী SQL চলে?**
     ```sql
     SELECT book.*, author.*
     FROM book
     INNER JOIN author ON book.author_id = author.id
     WHERE book.title ILIKE '%django%' OR author.name ILIKE '%django%';
     ```
   * *(এখানে `ILIKE` মানে বড় হাতের বা ছোট হাতের অক্ষর (`Django` / `django`) যা-ই লিখুক, সব মিলবে!)*

3. **`ordering_fields = ["price", "title", "id"]` (নিরাপত্তার তালা / Whitelist!)**
   * আপনি একটি **অনুমোদিত লিস্ট (Whitelist)** দিয়ে দিলেন। ইউজার শুধু `price`, `title` অথবা `id` দিয়েই সর্ট করতে পারবে:
     * `GET /api/books/?ordering=price` 👉 কম দাম থেকে বেশি দাম (Ascending)
     * `GET /api/books/?ordering=-price` 👉 বেশি দাম থেকে কম দাম (Descending — শুরুতে মাইনাস `-` দিলে উল্টো সাজায়!)
   * **ম্যাজিক (নিরাপত্তা):** কেউ যদি `?ordering=password` বা `?ordering=ultrapalta` দেয়, তাহলে সার্ভার ক্র্যাশ (`500 Error`) করবে না! DRF চুপচাপ সেটা **Ignore** করে ডিফল্ট অর্ডারে ডেটা পাঠিয়ে দেবে।

4. **`ordering = ["-id"]`**
   * ইউজার যদি URL-এ কোনো `?ordering=...` না দেয়, তাহলে ডিফল্টভাবে সবার শেষে যোগ হওয়া নতুন বইগুলো (`-id`) সবার ওপরে দেখাবে।

---

#### 🔍 `search_fields`-এ স্পেশাল চিহ্ন (Prefix) এর মানে কী?

সার্চটা কেমন হবে তা নিয়ন্ত্রণ করতে ফিল্ডের নামের আগে ছোট্ট একটা চিহ্ন দেওয়া যায়:

| Prefix | উদাহরণ | কী করে? (সহজ অর্থ) | SQL-এ কী হয়? |
| :---: | :--- | :--- | :--- |
| *(কিছু না দিলে)* | `"title"` | শব্দের **যেকোনো জায়গায়** মিললেই হবে (Contains) | `ILIKE '%django%'` |
| **`^`** | `"^title"` | নামটা অবশ্যই ওই শব্দ দিয়ে **শুরু** হতে হবে (Starts with) | `ILIKE 'django%'` *(বেশি ফাস্ট, Index কাজ করে!)* |
| **`=`** | `"=title"` | **হুবহু পুরোটা** মিলতে হবে (Exact match) | `= 'django'` |
| **`@`** | `"@title"` | **Full-text search** (শুধুমাত্র PostgreSQL-এ কাজ করে) | PostgreSQL Full-Text Search |

> **🔑 এক লাইনে সারসংক্ষেপ:**  
> হাতে `if/else` লিখে `get_queryset()` নোংরা না করে DRF-এর `SearchFilter` ও `OrderingFilter` ব্যবহার করলে মাত্র ৪ লাইন কোডেই **নিরাপদ, ক্লিন ও বাগ-মুক্ত** সার্চ এবং সর্টিং হয়ে যায়!


<br>
<br>

---

<br>
<br>

# 🟡 MEDIUM

## উদাহরণ ২ (Medium): `django-filter` এর `FilterSet` (রেঞ্জ, ক্যাটাগরি ও কাস্টম ফিল্টার)

<br>

### ❌ আগে (Bad — হাতে লেখা `if` ও ভ্যালিডেশনবিহীন কোড)

```python
def get_queryset(self):
    qs = Book.objects.all()
    p = self.request.query_params
    if p.get("category"):
        qs = qs.filter(category_id=p["category"])          # ❌ "abc" দিলে ValueError -> 500 error!
    if p.get("min_price"):
        qs = qs.filter(price__gte=p["min_price"])           # ❌ validation নেই
    if p.get("max_price"):
        qs = qs.filter(price__lte=p["max_price"])
    if p.get("is_published") == "true":                     # ❌ "True" বা "1" দিলে কাজ করবে না!
        qs = qs.filter(is_published=True)
    return qs
```

> **কী সমস্যা হচ্ছে?**
> 1. **কোনো টাইপ ভ্যালিডেশন নেই:** কেউ যদি URL-এ `?category=abc` বা `?min_price=hello` দেয়, তবে জ্যাঙ্গো `ValueError` থ্রো করে **`500 Internal Server Error`** দিয়ে সার্ভার ক্র্যাশ করাবে!
> 2. **ভঙ্গুর লজিক:** `is_published == "true"` চেক করলে কেউ `"True"` বা `"1"` পাঠালে ফিল্টার কাজই করবে না।
> 3. **কোড জ্যাম ও Swagger সমস্যা:** ২০টি ফিল্টার থাকলে `get_queryset()` বিশাল হয়ে যাবে এবং Swagger / OpenAPI ডকুমেন্টেশনে এই ফিল্টারগুলো অটোমেটিক দেখা যাবে না।

<br>

### ✅ পরে (Good — `django-filter` এর `FilterSet`)

```python
# filters.py
import django_filters as df
from .models import Book

class BookFilter(df.FilterSet):
    min_price = df.NumberFilter(field_name="price", lookup_expr="gte")  # price >= min_price
    max_price = df.NumberFilter(field_name="price", lookup_expr="lte")  # price <= max_price
    title = df.CharFilter(lookup_expr="icontains")                      # title ILIKE '%...%'

    class Meta:
        model = Book
        fields = ["category", "is_published"]   # সরাসরি exact match ফিল্ডগুলো

# views.py
from django_filters.rest_framework import DjangoFilterBackend

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author", "category")
    serializer_class = BookSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = BookFilter
```

<br>

---

<br>

### 💡 একদম সহজ বাংলায় ব্যাখ্যা (`FilterSet` কীভাবে কাজ করে?):

উদাহরণ ১-এ `SearchFilter` দিয়ে আমরা শুধু একটা সার্চ বক্সে (`?search=django`) খুঁজেছিলাম।  
কিন্তু রকমারি বা দারাজের **বাম পাশের ফিল্টার সাইডবারটার** কথা ভাবুন! সেখানে থাকে:
* **দামের রেঞ্জ:** সর্বনিম্ন ১০০ টাকা থেকে সর্বোচ্চ ৫০০ টাকা (`min_price=100&max_price=500`)
* **ক্যাটাগরি:** ফিকশন বা প্রোগ্রামিং (`category=3`)
* **পাবলিশড কি না:** হ্যাঁ/না (`is_published=true`)

এই সব **নির্দিষ্ট ফিল্ড-ভিত্তিক ফিল্টার** ক্লিনভাবে বানানোর জন্যই **`django-filter`**-এর **`FilterSet`** ব্যবহার করা হয়!

#### কোডের প্রতিটি অংশের সহজ অর্থ:

1. **`min_price = df.NumberFilter(field_name="price", lookup_expr="gte")`**
   * **`min_price`:** URL-এ ইউজার যে নামে প্যারামিটার পাঠাবে (`?min_price=100`)।
   * **`df.NumberFilter`:** এটি নিশ্চিত করে মানটি অবশ্যই **সংখ্যা (Number)** হতে হবে! কেউ `?min_price=abc` দিলে সার্ভার ক্র্যাশ (`500`) না করে সুন্দরভাবে **`400 Bad Request`** মেসেজ দেবে!
   * **`field_name="price"`:** `Book` মডেলে তো `min_price` নামে কোনো কলাম নেই, আসল কলামের নাম হলো `price` — তাই `field_name` দিয়ে আসল কলামটা চিনিয়ে দেওয়া হলো।
   * **`lookup_expr="gte"`:** Django ORM-এর `>=` (Greater Than or Equal)। অর্থাৎ ভেতরে তৈরি হবে: `Book.objects.filter(price__gte=100)`।

2. **`max_price = df.NumberFilter(field_name="price", lookup_expr="lte")`**
   * একইভাবে `lte` মানে `<=` (Less Than or Equal)। তৈরি হবে: `price__lte=500`।

3. **`title = df.CharFilter(lookup_expr="icontains")`**
   * এখানে ফিল্টারের নাম আর মডেলের ফিল্ডের নাম দুটোই `title`, তাই আলাদা করে `field_name="title"` লেখার দরকার পড়েনি! এটি `title__icontains` চালায়।

4. **`class Meta: fields = ["category", "is_published"]`**
   * যে ফিল্ডগুলোতে কোনো রেঞ্জ বা স্পেশাল লজিক নেই, শুধু **হুবহু মিল (Exact match)** দরকার—সেগুলো সরাসরি `Meta.fields`-এ লিস্ট করে দিলেই `django-filter` নিজেই তাদের জন্য সঠিক ফিল্টার (যেমন `BooleanFilter`, `ModelChoiceFilter`) বানিয়ে নেয়!
   * এতে `?is_published=true`, `?is_published=True`, বা `?is_published=1`—সবই স্বয়ংক্রিয়ভাবে কাজ করবে!

5. **ViewSet-এ যুক্ত করা (`DjangoFilterBackend` + `filterset_class`):**
   * `filter_backends = [DjangoFilterBackend]` — এই ভিউতে `django-filter` চালু করল।
   * `filterset_class = BookFilter` — আমাদের বানানো ফিল্টার ক্লাসটি জুড়ে দিল। এখন একসাথে সব ফিল্টার কাজ করবে:  
     👉 `GET /api/books/?min_price=100&max_price=500&category=3&title=python&is_published=true`

> **💡 প্রো টিপ:** আপনি চাইলে উদাহরণ ১ আর উদাহরণ ২ একসাথেও ব্যবহার করতে পারেন!
> ```python
> filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
> ```
> এতে একই API-তে ফিল্টারিং, সার্চিং এবং সর্টিং—তিনটাই একসাথে কাজ করবে!
