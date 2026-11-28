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
