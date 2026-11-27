# 1️⃣ Django REST Framework: Pagination Optimization Guide

> **কেন Pagination দরকার?**  
> ১ লক্ষ রেকর্ড একবারে পাঠালে **ডাটাবেজ (DB)**, **সার্ভার মেমোরি (RAM)** এবং **নেটওয়ার্ক**—তিনটাই চরম চাপে পড়ে। Pagination বড় ডেটাকে ছোট ছোট টুকরো (পেজ) করে পাঠায়, ফলে API হয় সুপার ফাস্ট এবং সার্ভার থাকে নিরাপদ।

---

<br>

# 🟢 EASY

## উদাহরণ ১ (Easy): কোনো Pagination নেই → `PageNumberPagination`

<br>

### ❌ আগে (Bad)

```python
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author")
    serializer_class = BookSerializer
    # pagination_class নেই, তাই সব বই একসাথে যাবে
```

> **কী হচ্ছে:** ডাটাবেজে ১ লক্ষ বই থাকলে ১ লক্ষটাই সিরিয়ালাইজ হয়ে রেসপন্সে যাবে। JSON রেসপন্স কয়েক মেগাবাইট (MB) হয়ে যাবে, সার্ভারের RAM ফুলে যাবে (Out of Memory ক্র্যাশ হতে পারে), আর ক্লায়েন্টের ব্রাউজার/অ্যাপ হ্যাং করবে।

<br>

### ✅ পরে (Good)

```python
# pagination.py
from rest_framework.pagination import PageNumberPagination

class StandardPagination(PageNumberPagination):
    page_size = 20                      # ডিফল্ট প্রতি পেজে ২০টি আইটেম
    page_size_query_param = "page_size" # ক্লায়েন্ট চাইলে ?page_size=50 দিতে পারবে
    max_page_size = 100                 # নিরাপত্তা: ক্লায়েন্ট যেন ১০০ এর বেশি না চায়

# views.py
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author").order_by("id")  # ✅ order_by জরুরি
    serializer_class = BookSerializer
    pagination_class = StandardPagination
```

**গ্লোবাল করতে চাইলে `settings.py` তে:**
```python
REST_FRAMEWORK = {
    "DEFAULT_PAGINATION_CLASS": "myapp.pagination.StandardPagination",
}
```

<br>

#### 💡 সহজ বাংলায় ব্যাখ্যা (Deep Dive):

1. **কীভাবে কাজ করে?**  
   ইউজার যখন `GET /api/books/?page=2&page_size=20` রিকোয়েস্ট পাঠায়, জ্যাঙ্গো ডাটাবেজে ২টি কুয়েরি চালায়:
   * প্রথম কুয়েরি: `SELECT COUNT(*) FROM book;` (মোট কতগুলো বই আছে জানার জন্য)
   * দ্বিতীয় কুয়েরি: `SELECT * FROM book ORDER BY id LIMIT 20 OFFSET 20;` (প্রথম ২০টা বাদ দিয়ে পরের ২০টা আনে)

2. **`order_by("id")` দেওয়া কেন এত জরুরি?**  
   ডাটাবেজে কোনো নির্দিষ্ট সাজানো ক্রম (Ordering) না বললে ডাটাবেজ নিজের ইচ্ছামতো যেকোনো সিরিয়ালে রো ফেরত দেয়। ফলে পেজ ১-এ যে বইটা দেখেছেন, পেজ ২-এ গিয়ে আবার সেই একই বই (Duplicate) দেখতে পারেন, অথবা কোনো বই মাঝখান থেকে গায়েব (Skip) হয়ে যেতে পারে! এজন্য DRF-ও ওয়ার্নিং দেয়।

3. **`max_page_size = 100` কেন দেওয়া হলো? (Security)**  
   আপনি যেহেতু `page_size_query_param = "page_size"` চালু করেছেন, কোনো হ্যাকার বা দুষ্ট ইউজার যদি URL-এ `?page_size=1000000` (১০ লক্ষ) লিখে রিকোয়েস্ট পাঠায়, তাহলে আপনার সার্ভার ডাউন (DoS Attack) হয়ে যেতে পারে! `max_page_size = 100` দিলে কেউ ১০ লক্ষ চাইলেও সার্ভার সর্বোচ্চ ১০০টির বেশি দেবে না।

<br>

#### ❓ কোডের ভেতরে আসলে কী ঘটছে এবং Response দেখতে কেমন হবে?

* **`queryset = Book.objects.select_related("author")`:** বইয়ের সাথে লেখকের নাম (`author_name`) আনতে ১টি SQL `JOIN` চালায় (যাতে N+1 সমস্যা না হয়)।
* **`serializer_class = BookSerializer`:** ডাটাবেজের পাইথন অবজেক্টগুলোকে JSON ফরম্যাটে রূপান্তর করে।
* **`pagination_class`:** ১ লক্ষ বই একসাথে না পাঠিয়ে মাত্র ২০টি করে ভাগ করে পাঠায়।

**❌ Pagination ছাড়া Response (বিশাল লিস্ট — ১ লক্ষ বই একসাথে):**
```json
[
    {
        "id": 1,
        "title": "Django Guide",
        "author_name": "Rahim"
    },
    {
        "id": 2,
        "title": "Python Mastery",
        "author_name": "Karim"
    }
    // ... এভাবে ১ লক্ষ বই একসাথে চলে আসবে!
]
```

**✅ `PageNumberPagination` সহ Response (মাত্র ২০টি বই):**
```json
{
    "count": 100000,
    "next": "http://127.0.0.1:8000/api/books/?page=2",
    "previous": null,
    "results": [
        {
            "id": 1,
            "title": "Django Guide",
            "author_name": "Rahim"
        }
        // ... মাত্র ২০টি বই!
    ]
}
```

> **সংক্ষেপে:** `select_related("author")` ঠেকায় **N+1 সমস্যা**, আর `pagination_class` ঠেকায় **বিশাল ডেটা লোড**। দুটো একসাথে ব্যবহার করলে API হয় **ডাবল ফাস্ট**! 🚀

<br>
<br>

---

<br>
<br>

# 🟡 MEDIUM

## উদাহরণ ২ (Medium): বড় টেবিলে `LimitOffset` ধীর → `CursorPagination`

<br>

### ❌ আগে

```python
from rest_framework.pagination import LimitOffsetPagination

class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Review.objects.order_by("-created_at")
    serializer_class = ReviewSerializer
    pagination_class = LimitOffsetPagination   # ?limit=20&offset=500000
```

> **কী হচ্ছে (৩টি বড় সমস্যা):**
> 1. **গভীর পেজে গিয়ে মারাত্মক স্লো (`OFFSET` সমস্যা):** `OFFSET 500000` মানে ডাটাবেজকে আগে প্রথম ৫ লক্ষ রো পড়ে ডিস্ক থেকে স্ক্যান করে ফেলে দিতে হয়, তারপর পরের ২০টা দেয়! পেজ যত গভীরে যাবে, কুয়েরি তত ধীর হবে।
> 2. **ডেটা ডুপ্লিকেট বা স্কিপ হওয়া:** আপনি যখন পেজ ১ পড়ছেন, তখন যদি নতুন ৫টি রিভিউ যোগ হয়, তবে পুরো লিস্ট ৫ ঘর নিচে সরে যাবে। তখন পেজ ২-এ গেলে পেজ ১-এর শেষ ৫টি রিভিউ আবার দেখতে পাবেন!
> 3. **ভারী `COUNT(*)` কুয়েরি:** কোটি কোটি রো থাকা টেবিলে প্রতি রিকোয়েস্টে পুরো টেবিল গুনে `COUNT(*)` বের করা খুব ব্যয়বহুল।

<br>

### ✅ পরে

```python
from rest_framework.pagination import CursorPagination

class ReviewCursorPagination(CursorPagination):
    page_size = 20
    ordering = "-created_at"     # ✅ unique ও indexed ফিল্ড হওয়া উচিত
    cursor_query_param = "cursor"

class ReviewViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Review.objects.select_related("user")
    serializer_class = ReviewSerializer
    pagination_class = ReviewCursorPagination
```

<br>

#### 💡 সহজ বাংলায় ব্যাখ্যা (বাস্তব উদাহরণ — বুকমার্ক):

মনে করুন আপনি ১০,০০০ পাতার একটি মোটা বই পড়ছেন।
* **`OFFSET` পদ্ধতি (বোকা পদ্ধতি):** আপনি প্রতিবার বই খুলে ১ নম্বর পাতা থেকে গুনে গুনে ৫,০০০ নম্বর পাতায় যান, তারপর ৫,০০১ থেকে ৫,০২০ পাতা পড়েন! পাতা যত বেশি হবে, গুনতে তত বেশি সময় লাগবে।
* **`Cursor` পদ্ধতি (বুকমার্ক পদ্ধতি):** আপনি যেখানে পড়া শেষ করেছেন সেখানে একটা **বুকমার্ক (Cursor)** রেখে দিলেন। পরের দিন সরাসরি ওই বুকমার্কটা খুলেই তার পরের ২০ পাতা পড়তে শুরু করলেন! প্রথম থেকে আর গুনতে হলো না!

**ভেতরে ডাটাবেজে কী ঘটে?**
1. রেসপন্সে `next` আর `previous` লিংক আসে, যেমন: `?cursor=cD0yMDI2LTEx...` (এটি আসলে আগের পেজের শেষ আইটেমের `created_at` সময়ের এনকোড করা মান)।
2. জ্যাঙ্গো এবার `OFFSET` ব্যবহার না করে সরাসরি **`WHERE` কন্ডিশন** চালায়:
   ```sql
   SELECT * FROM review
   WHERE created_at < '2026-11-27 10:30:00'
   ORDER BY created_at DESC
   LIMIT 21;
   ```
3. যেহেতু `created_at`-এ ডাটাবেজ **Index** আছে, তাই টেবিলে ১ কোটি রো থাকলেও ডাটাবেজ সরাসরি ওই সময়ের পরের ২০টি রো তুলে আনে—গতি সবসময় **একই রকম সুপার ফাস্ট (`O(log N)`)** থাকে!
4. এখানে কোনো `COUNT(*)` কুয়েরি চলে না।
5. মাঝখানে নতুন রিভিউ যোগ হলেও আপনার বুকমার্ক (`created_at < ...`) নড়বে না, তাই কোনো আইটেম ডুপ্লিকেট বা স্কিপ হবে না।

> ⚠️ **সীমাবদ্ধতা (Trade-off):** এখানে সরাসরি "পেজ ৫-এ যাও" বা "পেজ ৫০-এ যাও" (Random Page Jump) করা যায় না। শুধু **Next / Previous** যাওয়া যায়। তাই **Facebook/Instagram Feed, Infinite Scroll, Chat History**-এর জন্য এটাই সেরা।

<br>
<br>

---

<br>
<br>

# 🔴 HARD

## উদাহরণ ৩ (Hard): কাস্টম `NoCount` Pagination (`limit + 1` কৌশল)

<br>

### ❌ আগে

```python
class BookListView(APIView):
    def get(self, request):
        page = int(request.query_params.get("page", 1))
        size = 20
        books = list(Book.objects.filter(is_published=True))   # ❌ সব বই RAM এ লোড!
        total = len(books)
        data = books[(page - 1) * size : page * size]          # ❌ Python এ slice
        return Response({
            "total": total,
            "results": BookSerializer(data, many=True).data,
        })
```

> **কী হচ্ছে (ভয়াবহ অপচয় ও বাগ):**
> 1. `list(Book.objects...)` লেখার কারণে ১ লক্ষ বই ডাটাবেজ থেকে টেনে এনে RAM-এ ১ লক্ষ পাইথন অবজেক্ট বানানো হচ্ছে—তারপর মাত্র ২০টা রেখে বাকি ৯৯,৯৮০টা ফেলে দেওয়া হচ্ছে!
> 2. কোনো Input Validation নেই: কেউ `?page=abc` দিলে সার্ভার `500 Internal Server Error` দিয়ে ক্র্যাশ করবে, আর `?page=-5` দিলে পাইথনের নেগেটিভ স্লাইসিং হয়ে উল্টাপাল্টা ডেটা চলে আসবে!

<br>

### ✅ পরে

```python
# pagination.py
from rest_framework.pagination import BasePagination
from rest_framework.response import Response
from rest_framework.exceptions import NotFound

class NoCountPagination(BasePagination):
    """COUNT(*) ছাড়া, limit+1 কৌশলে has_next বের করে।"""
    default_size = 20
    max_size = 100

    def _int(self, value, default):
        try:
            v = int(value)
            return v if v > 0 else default
        except (TypeError, ValueError):
            return default

    def paginate_queryset(self, queryset, request, view=None):
        self.size = min(
            self._int(request.query_params.get("page_size"), self.default_size),
            self.max_size,
        )
        self.page = self._int(request.query_params.get("page"), 1)
        offset = (self.page - 1) * self.size

        # ✅ ম্যাজিক ট্রিক: size+1 (যেমন ২১টি) রো আনি। অতিরিক্ত ১টি থাকলেই বুঝব পরের পেজ আছে!
        rows = list(queryset[offset : offset + self.size + 1])
        if not rows and self.page > 1:
            raise NotFound("Page out of range")

        self.has_next = len(rows) > self.size
        return rows[: self.size]  # ✅ ক্লায়েন্টকে শুধু ২০টিই ফেরত দিই

    def get_paginated_response(self, data):
        return Response({
            "page": self.page,
            "page_size": self.size,
            "has_next": self.has_next,
            "has_previous": self.page > 1,
            "results": data,
        })

# views.py
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Book.objects.filter(is_published=True)
        .select_related("author")
        .order_by("id")
    )
    serializer_class = BookSerializer
    pagination_class = NoCountPagination
```

<br>

#### 💡 `limit + 1` কৌশল কীভাবে কাজ করে? (সহজ বাংলায় ব্যাখ্যা)

ধরুন আপনি ইউজারকে প্রতি পেজে **২০টি বই** দেখাবেন, আর নিচে একটি **"Load More"** বাটন দেখাবেন। এখন আপনার জানতে হবে—*"পরের পেজে কি আর কোনো বই আছে (`has_next`)?"*

* **সাধারণ উপায়:** ডাটাবেজে `SELECT COUNT(*) FROM book` চালিয়ে মোট বইয়ের সংখ্যা গোনা। কিন্তু টেবিলে ৫০ লক্ষ রো থাকলে `COUNT(*)` চালাতে অনেক সময় লাগে!
* **`limit + 1` বুদ্ধিমান কৌশল:**  
  আপনি ডাটাবেজকে ২০টি না চেয়ে **১টি বেশি, অর্থাৎ ২১টি (`size + 1`)** বই আনতে বলেন (`LIMIT 21`)!
  * **যদি ২১টি বই ফেরত আসে:** তার মানে ২০টির পরেও আরও বই আছে! 👉 `has_next = True`। এবার আপনি ২১ নম্বর বইটা বাদ দিয়ে শুধু প্রথম ২০টি (`rows[:20]`) ইউজারকে পাঠিয়ে দেন!
  * **যদি ২০টি বা তার কম বই ফেরত আসে:** তার মানে আর কোনো বই বাকি নেই! 👉 `has_next = False` ("Load More" বাটন হাইড হয়ে যাবে)।

**অন্যান্য সুবিধা:**
* ডাটাবেজে `COUNT(*)` কুয়েরি একদমই চলে না—মাত্র ১টি কুয়েরি (`LIMIT 21 OFFSET ...`)!
* `_int()` হেল্পার ফাংশন দিয়ে ইনপুট ভ্যালিডেশন করা হয়েছে, তাই `?page=abc` বা `?page=-5` দিলেও ক্র্যাশ করবে না, চুপচাপ ডিফল্ট পেজ `1` নেবে।
* `min(..., self.max_size)` দিয়ে সর্বোচ্চ ১০০টির লিমিট নিশ্চিত করা হয়েছে।

**কখন ব্যবহার করবেন?**  
যখন UI-তে মোট সংখ্যা (যেমন *"Total 5,42,100 results"*) দেখানোর দরকার নেই—শুধু **"Next"** বা **"Load More"** বাটন দেখাতে হবে এবং টেবিলটি অনেক বড়।

<br>
<br>

---

<br>

### 🎯 ইন্টারভিউ চিট শিট: কখন কোন Pagination ব্যবহার করবেন?

| Pagination এর ধরন | SQL কুয়েরি | `COUNT(*)` চলে? | পেজ জাম্প (`?page=5`) | কখন ব্যবহার করবেন? |
| :--- | :--- | :---: | :---: | :--- |
| **`PageNumberPagination`** | `LIMIT` + `OFFSET` | ✅ হ্যাঁ | ✅ হ্যাঁ | সাধারণ অ্যাডমিন প্যানেল, ছোট/মাঝারি টেবিল, যেখানে `1, 2, 3... 10` পেজ বাটন লাগে |
| **`CursorPagination`** | `WHERE col < val LIMIT` | ❌ না | ❌ না (শুধু Next/Prev) | বিশাল টেবিল, রিয়েল-টাইম ফিড (Facebook/X), Chat, Infinite Scroll |
| **`NoCountPagination` (`limit+1`)** | `LIMIT (N+1) OFFSET` | ❌ না | ✅ হ্যাঁ | বড় টেবিল যেখানে মোট সংখ্যা দেখানোর দরকার নেই, শুধু "Load More" বা "Next" লাগে |

> **ইন্টারভিউ প্রশ্ন:** *PageNumber vs Cursor কখন কোনটা ব্যবহার করবেন?*  
> **এক লাইনে উত্তর:** র‍্যান্ডম পেজ জাম্প (`page=5`) ও মোট সংখ্যা লাগলে **`PageNumberPagination`**, আর বিশাল ডেটা বা রিয়েল-টাইম ফিড/ইনফিনিট স্ক্রলের জন্য **`CursorPagination`**!
