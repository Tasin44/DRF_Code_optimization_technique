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

#### ❓ `limit` এবং `offset` আসলে কী? (সহজ বাংলায় বুঝুন)

একদম সহজ দুই শব্দের বাংলা অর্থ মনে রাখুন:
* **`limit`** = **কয়টা আইটেম নেব?** *(How many)*
* **`offset`** = **শুরু থেকে কয়টা বাদ দিয়ে (Skip করে) শুরু করব?** *(Skip how many)*

**বাস্তব উদাহরণ:** ধরুন আপনার লাইনে ১০০ জন মানুষ দাঁড়িয়ে আছে (১ থেকে ১০০ পর্যন্ত):
1. **`?limit=20&offset=0`** → শুরু থেকে ০ জন বাদ দাও, ২০ জনকে নাও 👉 **১ থেকে ২০ নম্বর**।
2. **`?limit=20&offset=20`** → প্রথম ২০ জন বাদ দাও (Skip), তার পরের ২০ জন নাও 👉 **২১ থেকে ৪০ নম্বর**।
3. **`?limit=20&offset=500000`** → প্রথম ৫ লক্ষ রিভিউ বাদ দাও, তার পরের ২০টি নাও 👉 **৫,০০,০০১ থেকে ৫,০০,০২০ নম্বর**।

**কেন `offset=500000` এত স্লো হয়?**  
ডাটাবেজ সরাসরি ৫,০০,০০১ নম্বরে লাফ দিয়ে যেতে পারে না! তাকে ১ থেকে শুরু করে গুনে গুনে ৫,০০,০০০টা রো পড়ে ডিস্ক থেকে স্ক্যান করে ফেলে দিতে হয়, তারপর ৫,০০,০০১ থেকে ২০টা রো আপনাকে দেয়! এজন্যই বড় টেবিলে `offset` যত বড় হয়, API তত স্লো হয়ে যায়—আর এর সমাধানই হলো **`CursorPagination`**!

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

#### ❓ `cursor_query_param = "cursor"` এর মানে কী?
এর মানে হলো **URL-এর কোয়েরি প্যারামিটারের নাম কী হবে তা ঠিক করে দেওয়া**।
* `cursor_query_param = "cursor"` দিলে URL হবে: `/api/reviews/?cursor=cD0yMDI2LTEx...`
* আর যদি বদলে `cursor_query_param = "c"` (বা `"next_token"`) দেন, তবে URL হবে: `/api/reviews/?c=cD0yMDI2LTEx...`
* *(নোট: DRF-এ এটির ডিফল্ট মান এমনিতেই `"cursor"` থাকে, তাই না লিখলেও কাজ করে; তবে কাস্টম নাম দিতে চাইলে এটি ব্যবহার করা হয়।)*

<br>
<br>

---

<br>
<br>

## উদাহরণ ২.৫ (Medium — Unique): কাস্টম Metadata সহ Pagination (`get_paginated_response` ওভাররাইড)

রিয়েল-ওয়ার্ল্ড ফ্রন্টএন্ড (React / Next.js / Flutter) ডেভেলপাররা প্রায়ই DRF-এর ডিফল্ট রেসপন্স (`count`, `next`, `previous`, `results`) পছন্দ করে না! কারণ ওখানে **`total_pages` (মোট কয়টি পেজ আছে)** বা **`current_page` (আমি এখন কত নম্বর পেজে আছি)** সরাসরি দেওয়া থাকে না!

<br>

### ❌ আগে (ডিফল্ট রেসপন্সের সীমাবদ্ধতা)

```json
{
    "count": 95,
    "next": "http://api.site.com/books/?page=3",
    "previous": "http://api.site.com/books/?page=1",
    "results": [...]
}
```
> **সমস্যা কী?** ফ্রন্টএন্ডে পেজিনেশন বার (`< 1 2 [3] 4 5 >`) দেখাতে গেলে ফ্রন্টএন্ড ডেভেলপারকে নিজেই `Math.ceil(count / page_size)` করে মোট পেজ বের করতে হয়, আবার URL পার্স করে বর্তমান পেজ নম্বর বের করতে হয়।

<br>

### ✅ পরে (কাস্টম Metadata সহ ক্লিন Pagination)

```python
# pagination.py
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomMetaPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data):
        return Response({
            "meta": {
                "total_items": self.page.paginator.count,      # মোট আইটেম (যেমন: 95)
                "total_pages": self.page.paginator.num_pages,  # মোট পেজ (যেমন: 5)
                "current_page": self.page.number,              # বর্তমান পেজ (যেমন: 2)
                "page_size": self.get_page_size(self.request), # প্রতি পেজে কয়টি (যেমন: 20)
                "has_next": self.page.has_next(),              # পরের পেজ আছে কি না (True/False)
                "has_previous": self.page.has_previous(),      # আগের পেজ আছে কি না (True/False)
            },
            "links": {
                "next": self.get_next_link(),
                "previous": self.get_previous_link(),
            },
            "results": data,
        })

# views.py
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author").order_by("id")
    serializer_class = BookSerializer
    pagination_class = CustomMetaPagination
```

**এখন JSON রেসপন্স কেমন আসবে?**
```json
{
    "meta": {
        "total_items": 95,
        "total_pages": 5,
        "current_page": 2,
        "page_size": 20,
        "has_next": true,
        "has_previous": true
    },
    "links": {
        "next": "http://127.0.0.1:8000/api/books/?page=3",
        "previous": "http://127.0.0.1:8000/api/books/?page=1"
    },
    "results": [...]
}
```

<br>

#### 💡 সহজ বাংলায় ব্যাখ্যা:
1. **`get_paginated_response(self, data)`:** DRF-এ এটিই সেই মেথড যা ফাইনাল JSON স্ট্রাকচার তৈরি করে। এটিকে ওভাররাইড করে আপনি নিজের কোম্পানির স্ট্যান্ডার্ড অনুযায়ী যেকোনো সুন্দর ফরম্যাট বানাতে পারেন।
2. **কোনো বাড়তি কুয়েরি চলে না!** `self.page.paginator.num_pages`, `self.page.number`, `has_next()` — এগুলো সব আগেই আনা `count` থেকে পাইথনেই হিসাব হয়, ডাটাবেজে কোনো নতুন কুয়েরি যায় না।
3. **কখন ব্যবহার করবেন?** যখন ফ্রন্টএন্ডে নম্বরওয়ালা পেজিনেশন বার (`1, 2, 3, ..., 10`) বা *"Showing page 2 of 5"* দেখাতে হবে—প্রায় সব প্রোডাকশন প্রজেক্টেই এই প্যাটার্ন ব্যবহার করা হয়!

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

#### ❓ `data = books[(page - 1) * size : page * size]` লাইনটিতে কী হচ্ছে?
এটি হলো পাইথনের **List Slicing (`books[start : end]`)**, যা `books` লিস্ট থেকে নির্দিষ্ট পেজের ২০টি বই কেটে আলাদা করে (`size = 20` ধরে):
* **`page = 1`** → `books[(1-1)*20 : 1*20]` → **`books[0 : 20]`** (প্রথম ২০টি বই)
* **`page = 2`** → `books[(2-1)*20 : 2*20]` → **`books[20 : 40]`** (পরের ২০টি বই)
* **`page = 3`** → `books[(3-1)*20 : 3*20]` → **`books[40 : 60]`**

**এখানে ❌ (খারাপ) কেন?**  
অঙ্কটা ঠিক আছে, কিন্তু আগের লাইনে `list(...)` করার ফলে পুরো ১ লক্ষ বই আগে **RAM-এ লোড** হয়ে গেছে, তারপর পাইথনে বসে ২০টা কেটে নিয়ে বাকি ৯৯,৯৮০টা ফেলে দেওয়া হচ্ছে! *(অথচ `list()` না করে সরাসরি **QuerySet**-এ স্লাইস করলে জ্যাঙ্গো ডাটাবেজে `LIMIT 20 OFFSET 20` চালাত!)*

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

#### 🔍 `NoCountPagination` ক্লাসের লাইন-বাই-লাইন সহজ ব্যাখ্যা:

1. **ক্লাস সেটআপ (`BasePagination`, `default_size`, `max_size`):**
   * `class NoCountPagination(BasePagination):` — DRF-এর একদম বেস ক্লাস থেকে নিজের কাস্টম পেজিনেশন বানাচ্ছি।
   * `default_size = 20`, `max_size = 100` — ইউজার কিছু না বললে ২০টি, আর বেশি চাইলেও সর্বোচ্চ ১০০টির বেশি দেব না।

2. **ইনপুট নিরাপদ করার হেল্পার ফাংশন (`_int`):**
   ```python
   def _int(self, value, default):
       try:
           v = int(value)
           return v if v > 0 else default
       except (TypeError, ValueError):
           return default
   ```
   * URL থেকে আসা মান (`value`) সবসময় স্ট্রিং হয় (যেমন `"2"`, `"abc"`, `"-5"` বা `None`)।
   * এটি মানটিকে পূর্ণসংখ্যা (`int`) বানায়। যদি শূন্য বা মাইনাস (`-5`) হয়, অথবা `"abc"` / `None` হওয়ায় এরর খায়—তাহলে সার্ভার ক্র্যাশ না করে চুপচাপ `default` মান ফেরত দেয়!

3. **`paginate_queryset()` — আসল কাজ এখানেই হয়:**
   * `self.size = min(self._int(request.query_params.get("page_size"), self.default_size), self.max_size)`  
     👉 URL থেকে `page_size` নেয় (না দিলে ২০), তারপর `min(..., 100)` দিয়ে নিশ্চিত করে যেন ১০০-এর বেশি না হয়।
   * `self.page = self._int(request.query_params.get("page"), 1)`  
     👉 URL থেকে `page` নম্বর নেয়, না দিলে বা ভুল দিলে `1` ধরে নেয়।
   * `offset = (self.page - 1) * self.size`  
     👉 শুরু থেকে কয়টা রো বাদ দেবে (Skip করবে) তা বের করে। যেমন পেজ ২ আর সাইজ ২০ হলে: `(2 - 1) * 20 = 20`।
   * `rows = list(queryset[offset : offset + self.size + 1])`  
     👉 **আসল ম্যাজিক!** সরাসরি QuerySet-এ স্লাইস করায় জ্যাঙ্গো ডাটাবেজে `LIMIT 21 OFFSET 20` চালায় (সব ডেটা RAM-এ আনে না, শুধু ২১টা আনে!)।
   * `if not rows and self.page > 1: raise NotFound("Page out of range")`  
     👉 ধরুন মোট পেজ আছে ৫টা, কিন্তু ইউজার দিল `?page=99`। তখন `rows` খালি হবে এবং `page > 1`, তাই `404 Not Found` দেখাবে! *(তবে পেজ ১ খালি হলে—অর্থাৎ টেবিলে কোনো বই-ই না থাকলে—৪০৪ না দিয়ে খালি লিস্ট `[]` দেবে!)*
   * `self.has_next = len(rows) > self.size`  
     👉 যদি ২১টি রো আসে (`21 > 20`), তবে `True` (পরের পেজ আছে)। ২০টি বা কম এলে `False` (এটাই শেষ পেজ)।
   * `return rows[: self.size]`  
     👉 বাড়তি ২১ নম্বর রো-টা কেটে ফেলে শুধু প্রথম ২০টি রো সিরিয়ালাইজারের কাছে পাঠায়।

4. **`get_paginated_response(self, data)` — ফাইনাল JSON বানানো:**
   * সিরিয়ালাইজার ওই ২০টি রো-কে JSON (`data`) বানিয়ে এই মেথডে দেয়।
   * এটি `page`, `page_size`, `has_next`, `has_previous` (`page > 1` হলেই আগের পেজ আছে!) এবং `results`-কে একসাথে গুছিয়ে ক্লায়েন্টকে রিটার্ন করে।

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
