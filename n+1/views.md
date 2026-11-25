# Django REST Framework: N+1 Query Optimization Guide

---

<br>

# 🟢 EASY

## উদাহরণ ১ (Easy): যদি ForeignKey এর নাম serializer এ দেখানো হয় → সমাধান `select_related`

<br>

### ❌ আগে (Bad)

```python
# serializers.py
from models import Review
import serial

class BookSerializer(serializers.ModelSerializer):
    author_name = serializers.CharField(source="author.name", read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "author_name"]

# views.py
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.all()          # ❌ author আনা হয়নি
    serializer_class = BookSerializer
```

**কী হচ্ছে:**
* ১টা query: `SELECT * FROM book` (ধরো ৫০টা বই)
* প্রতিটা বইয়ের জন্য `book.author.name` পড়তে গেলে Django তখন আলাদা `SELECT * FROM author WHERE id = ?` চালায়।
* **মোট 51 query।**

<br>

### ✅ পরে (Good)

```python
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.select_related("author")   # ✅ JOIN
    serializer_class = BookSerializer
```

**কী হচ্ছে:** Django `book INNER JOIN author` করে একবারেই author এর ডেটা এনে রাখে। `book.author` পড়লে আর DB তে যায় না। **মোট 1 query।**

<br>
<br>

---

<br>
<br>

## উদাহরণ ২ (Easy): Author এর সাথে তার সব বইয়ের নাম → `prefetch_related`

<br>

### ❌ আগে

```python
class AuthorSerializer(serializers.ModelSerializer):
    book_titles = serializers.SerializerMethodField()

    class Meta:
        model = Author
        fields = ["id", "name", "book_titles"]

    def get_book_titles(self, obj):
        return [b.title for b in obj.books.all()]   # ❌ প্রতি author এ নতুন query

class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Author.objects.all()
    serializer_class = AuthorSerializer
```

> **সম্পর্ক বিশ্লেষণ:**  
> * **Book to Author** = Many to One (One to One নয়)  
> * **Author to Book** = One to Many (Reverse relation)  
>  
> **কী হচ্ছে:** reverse relation (`author.books`) এ `select_related` কাজ করে না। প্রতি author এর জন্য আলাদা `SELECT ... FROM book WHERE author_id = ?`। **মোট 1 + N query।**

<br>

### ✅ পরে

```python
class AuthorViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Author.objects.prefetch_related("books")   # ✅
    serializer_class = AuthorSerializer
```

**কী হচ্ছে: মোট ২টা query চলে:**
```sql
SELECT * FROM author;
SELECT * FROM book WHERE author_id IN (1, 2, 3, ...);
```
তারপর Django Python এ বইগুলো সঠিক author এর সাথে জুড়ে দেয়। `obj.books.all()` তখন cache থেকে আসে।

<br>

#### এটি কীভাবে কাজ করে:

* **কেন `select_related` কাজ করে না?**  
  `select_related` কাজ করে SQL JOIN দিয়ে (Single-valued relationship যেমন: ForeignKey বা OneToOneField এর ক্ষেত্রে)।  
  কিন্তু Author থেকে Book হলো One to Many (একটি Author এর একাধিক Book থাকতে পারে)। SQL JOIN করলে ডেটা ডুপ্লিকেট হয়ে যায়, তাই Django Reverse ForeignKey বা ManyToMany তে `select_related` সাপোর্ট করে না।

* **কেন `prefetch_related` ব্যবহার করা হয়?**  
  এটি SQL JOIN করে না। বরং ২টি আলাদা কুয়েরি চালায়:  
  1. প্রথমে সব লেখক আনে: `SELECT * FROM author`  
  2. এরপর ওই সব লেখকের আইডি দিয়ে একবারে সব বই আনে: `SELECT * FROM book WHERE author_id IN (1, 2, 3, ...)`  
  তারপর পাইথন মেমোরিতে (Python memory) প্রতিটি বইকে তার নির্দিষ্ট author অবজেক্টের ক্যাশে (`_prefetched_objects_cache`) সাজিয়ে রেখে দেয়। এর ফলে পরবর্তীতে যখন লুপে `obj.books.all()` কল করা হয়, তখন ডেটাবেজে আর কোনো নতুন কুয়েরি যায় না, পাইথন ক্যাশ থেকেই সরাসরি রেজাল্ট দেয় (N+1 সমস্যা দূর হয়)।

<br>
<br>

---

<br>
<br>

# 🟡 MEDIUM

## উদাহরণ ৩ (Medium): ManyToMany tags → `prefetch_related`

<br>

### ❌ আগে

```python
class BookSerializer(serializers.ModelSerializer):
    tags = serializers.SlugRelatedField(many=True, read_only=True, slug_field="name")
    author_name = serializers.CharField(source="author.name")

    class Meta:
        model = Book
        fields = ["id", "title", "author_name", "tags"]

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.all()                # ❌ author আর tags দুটোতেই N+1
    serializer_class = BookSerializer
```

> **কী হচ্ছে:** এখানে দুটো আলাদা N+1 একসাথে আছে। একটা author এর জন্য, আরেকটা tags এর জন্য। ৫০ বইয়ে প্রায় ১০১ query।

<br>

### ✅ পরে applying `prefetch_related`

```python
class BookViewset(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Book.objects
        .select_related("author")
        .prefetch_related("tags")
    )
    serializer_class = BookSerializer
```

<br>

> ### ❓ Why I'm using select_related for author, isn't it many to one relationship?
> 
> **হ্যাঁ, এটি Many-to-One সম্পর্ক, আর ঠিক এই কারণেই এখানে `select_related` ব্যবহার করা যায় এবং করা উচিত!**
> 
> **বিস্তারিত ব্যাখ্যা (সহজ কনসেপ্ট):**  
> `select_related` কোন কোন ক্ষেত্রে কাজ করে—সেটা বোঝার মূল সূত্র হলো: *"যে মডেল থেকে কুয়েরি করছেন, তার প্রতিটি রেকর্ডের বিপরীতে যার ডেটা আনছেন সে কি মাত্র একজন (Single Object)?"*  
> এখানে আপনি কুয়েরি করছেন `Book` টেবিল থেকে (`Book.objects...`):
> 
> 1. **Book-এর দিক থেকে Author কয়জন?**  
>    ১টি বইয়ের (One Book) লেখক মাত্র ১ জন (Single Author)। অর্থাৎ, প্রতিটি Book রো (row)-এর সাথে ঠিক ১টি Author রো যুক্ত।
> 
> 2. **ডাটাবেজে কী ঘটে?**  
>    যেহেতু ১টি বইয়ের সাথে মাত্র ১ জন লেখক থাকে, তাই SQL সহজেই একটি JOIN অপারেশন চালাতে পারে:
>    ```sql
>    SELECT book.*, author.* 
>    FROM book 
>    JOIN author ON book.author_id = author.id;
>    ```
>    এতে ডেটা ডুপ্লিকেট হওয়ার বা কোনো সমস্যা হওয়ার সুযোগ নেই। একটি মাত্র SQL কুয়েরিতেই সব বই এবং তাদের লেখকদের নাম একসাথে চলে আসে।
> 
> 3. **কনফিউশনটা কোথায় তৈরি হয়?**  
>    * `Book.objects.select_related("author")` ✅ (কাজ করবে): কারণ এখানে Book → Author (Forward ForeignKey)। প্রতিটি বইয়ের জন্য লেখক মাত্র ১ জন (Single object)। তাই SQL JOIN সম্ভব।  
>    * `Author.objects.select_related("books")` ❌ (কাজ করবে না): কারণ এখানে Author → Book (Reverse ForeignKey / One-to-Many)। ১ জন লেখকের একাধিক বই (Multiple objects) থাকতে পারে। একাধিক অবজেক্ট থাকলে `select_related` কাজ করে না, তখন `prefetch_related` ব্যবহার করতে হয়।

<br>

#### সংক্ষেপে মনে রাখার গোল্ডেন রুল:

| আপনি যেখান থেকে রিলেশন টানছেন | সম্পর্ক | যা রিটার্ন করে | কী ব্যবহার করবেন? |
| :--- | :--- | :--- | :--- |
| **Book → Author** (Forward ForeignKey) | Many-to-One | ১ জন (Single) | `select_related` ✅ |
| **Author → Book** (Reverse ForeignKey) | One-to-Many | একাধিক (List) | `prefetch_related` ✅ |
| **Book ↔ Tag** (ManyToManyField) | Many-to-Many | একাধিক (List) | `prefetch_related` ✅ |

**কী হচ্ছে:** মোট ২টা query (১টা JOIN সহ book+author, আরেকটা tag এর জন্য)। নিয়ম: FK/OneToOne হলে `select_related`, M2M/reverse FK হলে `prefetch_related`।

<br>
<br>

---

<br>
<br>

## উদাহরণ ৪ (Medium): চেইন করা FK (OrderItem → Book → Author, Category) → double underscore

<br>

### ❌ আগে

```python
class OrderItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title")
    author = serializers.CharField(source="book.author.name")
    category = serializers.CharField(source="book.category.name")

    class Meta:
        model = OrderItem
        fields = ["id", "quantity", "book_title", "author", "category"]

class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrderItem.objects.all()   # ❌ প্রতি row তে book, author, category = ৩ query
    serializer_class = OrderItemSerializer
```

<br>

> ### ❓ প্রশ্ন ১: ১০০ item হলে ১ + (১০০ × ৩) = ৩০১ কুয়েরি কীভাবে হচ্ছে?
> 
> **সহজ হিসাব:**  
> * **মূল কুয়েরি (১টি):**  
>   প্রথমে সবগুলো OrderItem আনার জন্য জ্যাঙ্গো ১টি কুয়েরি চালায়:  
>   `SELECT * FROM order_item;` (ধরি, ১০০টি রো ফেরত পেল)।
> 
> * **লুপের ভেতরের কুয়েরি (১০০ × ৩ = ৩০০টি):**  
>   প্রতিটি OrderItem যখন সিরিয়ালাইজ হতে যায়, তখন তিনটি আলাদা রিলেশন এক্সেস করা হয়:  
>   1. `source="book.title"` এর জন্য জ্যাঙ্গো ডাটাবেজে যায়: `SELECT * FROM book WHERE id = ?;` (১টি কুয়েরি)  
>   2. `source="book.author.name"` এর জন্য লেখকের খোঁজে যায়: `SELECT * FROM author WHERE id = ?;` (১টি কুয়েরি)  
>   3. `source="book.category.name"` এর জন্য ক্যাটাগরির খোঁজে যায়: `SELECT * FROM category WHERE id = ?;` (১টি কুয়েরি)  
> 
>   যেহেতু প্রতিটি আইটেমের জন্য ৩টি করে কুয়েরি হচ্ছে, তাই ১০০টি আইটেমের জন্য মোট: `১০০ × ৩ = ৩০০টি` কুয়েরি।
> 
> * **সর্বমোট:** মূল কুয়েরি (১টি) + লুপের ভেতর (৩০০টি) = **মোট ৩০১টি কুয়েরি!** (ভয়ংকর N+1 সমস্যা)।

<br>

### ✅ পরে

```python
class OrderItemViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = OrderItem.objects.select_related(
        "book__author",       # book এবং author দুটোই JOIN হবে
        "book__category",
    )
    serializer_class = OrderItemSerializer
```

**কী হচ্ছে:** `__` দিয়ে যত গভীরে যাওয়া যায়, সব JOIN হয়ে ১টা query তে আসে। **301 → 1**।

<br>

> ### ❓ প্রশ্ন ২: `__` (double underscore) কীভাবে কাজ করে?
> 
> জ্যাঙ্গো ORM-এ `__` (double underscore) মানে হলো **"এক টেবিল থেকে আরেক টেবিলে লাফ দেওয়া"** (Follow the foreign key relationship)।  
> এসকিউএল (SQL) এর ভাষায় এটি একটির পর আরেকটি টেবিলকে JOIN করে। যেমন:  
> * `"book__author"` লিখলে ডাটাবেজে ঘটে: `order_item` টেবিলের সাথে `book` টেবিল JOIN হয়, এবং সেই `book` টেবিলের সাথে আবার `author` টেবিল JOIN হয়।  
> * `"book__category"` লিখলে: `book` টেবিলের সাথে `category` টেবিলও JOIN হয়ে যায়।  
> 
> ফলে মাত্র **১টি মাত্র SQL কুয়েরিতেই ৪টি টেবিল** (`order_item`, `book`, `author`, `category`) একসাথে JOIN হয়ে সব ডেটা একবারে চলে আসে (৩০১ কুয়েরি থেকে নেমে ১ কুয়েরি হয়ে যায়)।

<br>

> ### ❓ প্রশ্ন ৩: author আর category ফেচ করলাম, কিন্তু title আর quantity কেন `__` দিয়ে লেখা হলো না?
> 
> ১. **quantity কেন লেখা হয়নি?**  
> `quantity` তো অন্য কোনো টেবিলে নেই! এটি সরাসরি `OrderItem` টেবিলেরই নিজস্ব একটি কলাম/ফিল্ড। যেহেতু আমরা `OrderItem.objects.all()` বা `OrderItem.objects.select_related(...)` লিখছি, তাই `OrderItem` টেবিলের সব কলাম (`id`, `quantity` ইত্যাদি) এমনিতেই ডাটাবেজ থেকে চলে আসে। এর জন্য কোনো JOIN বা `__` লাগে না।
> 
> ২. **title কেন লেখা হয়নি?**  
> `title` হলো `Book` টেবিলের নিজস্ব একটি সাধারণ ফিল্ড/কলাম। আমরা যখন `select_related("book__author")` লিখি, তখন জ্যাঙ্গো পুরো `Book` টেবিলটাকেই JOIN করে এনে ফেলে। আর পুরো `Book` টেবিল যখন মেমোরিতে চলে আসে, তখন তার ভেতরের সব সাধারণ ফিল্ড—যেমন: `book.id`, `book.title`, `book.price`—সব ফিল্ড স্বয়ংক্রিয়ভাবেই চলে আসে!  
> 
> *মনে রাখবেন: `select_related` শুধুমাত্র Foreign Key বা One-to-One রিলেশন ফিল্ডের জন্য কাজ করে। এটি কোনো সাধারণ কলামের জন্য কাজ করে না।*

<br>
<br>

---

<br>
<br>

# 🔴 ADVANCED

## উদাহরণ ৫ (Advanced): শুধু approved review লোড করা → `Prefetch` object + `to_attr`

<br>

### ❌ আগে

```python
class BookSerializer(serializers.ModelSerializer):
    approved_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ["id", "title", "approved_reviews"]

    def get_approved_reviews(self, obj):
        # ❌ .filter() সবসময় নতুন query চালায়
        qs = obj.reviews.filter(is_approved=True)
        return [{"rating": r.rating} for r in qs]

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.prefetch_related("reviews")   # ❌ prefetch করেও লাভ নেই
    serializer_class = BookSerializer
```

> **কী হচ্ছে (ইন্টারভিউর ফেভারিট gotcha):**  
> `prefetch_related("reviews")` করা হলো ঠিকই। কিন্তু `obj.reviews.filter(...)` করলে Django prefetch cache ব্যবহার করে না, নতুন SQL চালায়। উল্টো আরও খারাপ হলো, কারণ prefetch এর query টাও বেকার গেল।

<br>

### ✅ পরে

```python
from django.db.models import Prefetch

class BookSerializer(serializers.ModelSerializer):
    approved_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ["id", "title", "approved_reviews"]

    def get_approved_reviews(self, obj):
        return [{"rating": r.rating} for r in obj.approved_reviews_list]  # ✅ cache থেকে

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.prefetch_related(
        Prefetch(
            "reviews",
            queryset=Review.objects.filter(is_approved=True),
            to_attr="approved_reviews_list",     # আলাদা নামে রাখি
        )
    )
    serializer_class = BookSerializer
```

<br>

#### বিস্তারিত ব্যাখ্যা:

1. **মূল সমস্যাটা কী ছিল?**  
   `prefetch_related('reviews')` করলে জ্যাঙ্গো মেমোরির ক্যাশে সবগুলো review রেখে দেয়। আপনি যখন `obj.reviews.all()` লিখবেন, তখন সে ক্যাশ থেকে ডেটা দেবে। কিন্তু আপনি যখনই ক্যাশের উপর আবার `.filter(...)` বা `.exclude(...)` চালাবেন, জ্যাঙ্গো ক্যাশ বাদ দিয়ে সরাসরি ডাটাবেজে গিয়ে আবার নতুন একটা SQL কুয়েরি চালাবে!  
   *ফলাফল (Double Loss):* ১০০টি বই থাকলে ১০০ বার নতুন SQL চলল এবং আগের prefetch কুয়েরিটা পুরোটাই নষ্ট হলো।

2. **`Prefetch()` অবজেক্ট এবং `to_attr` কীভাবে সমাধান করে?**  
   * **কুয়েরি লেভেলে ফিল্টারিং (SQL Query):**  
     ```sql
     -- ১ নম্বর কুয়েরি: সব বই আনে
     SELECT * FROM book;
     -- ২ নম্বর কুয়েরি: একবারে শুধু approved রিভিউগুলো আনে
     SELECT * FROM review WHERE is_approved = TRUE AND book_id IN (1, 2, 3, ...);
     ```
   * **`to_attr="approved_reviews_list"` এর কাজ:**  
     সাধারণভাবে জ্যাঙ্গো ডেটা এনে `obj.reviews.all()`-এ ক্যাশ করে রাখে। কিন্তু `to_attr` ব্যবহার করায় জ্যাঙ্গো প্রতিটি Book অবজেক্টের গায়ে পাইথনের একটি সাধারণ লিস্ট (Plain Python List) হিসেবে `approved_reviews_list` নামে বসিয়ে দেয়।
   * **সিরিয়ালাইজারে ক্যাশ ব্যবহার:**  
     `obj.approved_reviews_list` একটি সাধারণ পাইথন লিস্ট হওয়ায় মেমোরি থেকেই নিমেষেই ডেটা প্রসেস হয়ে যায়, কোনো নতুন ডাটাবেজ হিট যায় না।

<br>

> **সারসংক্ষেপ (এক নজরে):**  
> * `obj.relation.filter(...)` লুপে চালালে prefetch ক্যাশ ভেঙে যায় এবং নতুন কুয়েরি চলে।  
> * কাস্টম শর্তে ফিল্টার করা ডেটা prefetch করতে চাইলে `Prefetch(..., queryset=..., to_attr=...)` ব্যবহার করতে হয়।  
> * এতে কুয়েরি সংখ্যা ১০০+ থেকে কমে মাত্র **২টি**-তে নেমে আসে!

<br>
<br>

---

<br>

### 💡 `to_attr="approved_reviews_list"` আরও সহজে বোঝার রিয়েল-লাইফ ব্যাখ্যা (Deep Dive):

> **বাস্তব জীবনের রূপক (Analogy):**  
> মনে করুন আপনার কাছে একটি **বই (Book Object)** আছে এবং ডাটাবেজ হলো অনেক দূরের একটি **গোডাউন**।

#### ১. সাধারণ অবস্থায় কী সমস্যা হচ্ছিল (`to_attr` ছাড়া)?
* আপনি যখন শুধু `prefetch_related("reviews")` লিখেছিলেন, জ্যাঙ্গো গোডাউন থেকে বইয়ের **সব রিভিউ** এনে `obj.reviews.all()` নামক একটি ড্রয়ারে রেখে দিয়েছিল।
* কিন্তু সিরিয়ালাইজারে গিয়ে যখন আপনি বললেন: `obj.reviews.filter(is_approved=True)` — জ্যাঙ্গো হাতের কাছের ড্রয়ারে না খুঁজে আবার দৌড়ে দূরের **গোডাউনে (Database)** চলে গেল! 
* ফলে যতগুলো বই ছিল, ততবার ডাটাবেজে আলাদা নতুন কুয়েরি চলল (N+1 সমস্যা থেকে গেল)।

#### ২. `to_attr="approved_reviews_list"` কীভাবে সমাধান করল?
আপনি যখন লিখলেন:
```python
Prefetch(
    "reviews",
    queryset=Review.objects.filter(is_approved=True),  # গোডাউন থেকেই শুধু অনুমোদিতগুলো আনো
    to_attr="approved_reviews_list"                    # এনে এই নামের নতুন পকেটে রাখো
)
```
* **`to_attr` মানে হলো রানটাইমে নতুন একটি ভেরিয়েবল বা পকেট বানিয়ে দেওয়া।**
* জ্যাঙ্গো ডাটাবেজ থেকে একবারে শুধু `is_approved=True` রিভিউগুলো আনল।
* তারপর প্রতিটি `book` অবজেক্টের গায়ে পাইথনের একটি সাধারণ লিস্ট হিসেবে জুড়ে দিল:
  ```python
  # জ্যাঙ্গো মেমোরিতে প্রতিটি বইয়ের সাথে স্বয়ংক্রিয়ভাবে এটি করে দেয়:
  book.approved_reviews_list = [Review(rating=5), Review(rating=4)]
  ```
  *(লক্ষ্য করুন: `Book` মডেলে কিন্তু এই নামে কোনো ফিল্ড নেই, এটি মেমোরিতে সাময়িকভাবে তৈরি হওয়া একটি সাধারণ পাইথন লিস্ট)।*

#### ৩. সিরিয়ালাইজারে ক্যাশ কীভাবে কাজ করছে?
```python
def get_approved_reviews(self, obj):
    # obj মানে book অবজেক্ট
    return [{"rating": r.rating} for r in obj.approved_reviews_list]
```
যেহেতু `obj.approved_reviews_list` একটি সাধারণ পাইথন লিস্ট (যেমন: `[1, 2, 3]`), তাই এর ওপর যখন লুপ ঘোরে, পাইথনের আর ডাটাবেজে যাওয়ার কোনো প্রয়োজনই পড়ে না। সে র‍্যাম (RAM / Memory) থেকে নিমেষেই ডেটা প্রসেস করে ফেলে।

#### 🔑 মূল দুটি কথা মনে রাখুন:
1. **`queryset=...`** → ডাটাবেজ থেকে **কী ফিল্টার করে** আনবে তা ঠিক করে।
2. **`to_attr="নাম"`** → সেই ফিল্টার করা ডেটা প্রতিটি অবজেক্টের গায়ে **কোন নামের পাইথন লিস্টে** ক্যাশ করে রাখবে তা ঠিক করে।


<br>
<br>

---

<br>
<br>

## উদাহরণ ৬ (Advanced): SerializerMethodField এ count/avg → `annotate`

<br>

### ❌ আগে

```python
class BookSerializer(serializers.ModelSerializer):
    review_count = serializers.SerializerMethodField()
    avg_rating = serializers.SerializerMethodField()

    class Meta:
        model = Book
        fields = ["id", "title", "review_count", "avg_rating"]

    def get_review_count(self, obj):
        return obj.reviews.count()                               # ❌ query

    def get_avg_rating(self, obj):
        return obj.reviews.aggregate(a=Avg("rating"))["a"]       # ❌ আরেকটা query

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.all()
    serializer_class = BookSerializer
```

> **কী হচ্ছে:** প্রতি বইয়ে ২টা করে নতুন query চলে। ১০০ বইয়ে `১ + (১০০ × ২) = ২০১` query (N+1 সমস্যা)।

<br>

### ✅ পরে

```python
from django.db.models import Count, Avg

class BookSerializer(serializers.ModelSerializer):
    review_count = serializers.IntegerField(read_only=True)
    avg_rating = serializers.FloatField(read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "review_count", "avg_rating"]

class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.annotate(
        review_count=Count("reviews"),
        avg_rating=Avg("reviews__rating"),
    )
    serializer_class = BookSerializer
```

**কী হচ্ছে:** `GROUP BY book.id` সহ ১টা SQL এ `count` আর `avg` দুটোই চলে আসে। প্রতিটা Book অবজেক্টে `review_count` আর `avg_rating` অ্যাট্রিবিউট হিসেবে বসে যায়। **২০১ → ১**।

<br>

> ⚠️ **সতর্কতা:** একসাথে একাধিক multi-valued relation এ Count করলে (যেমন reviews আর tags) সংখ্যা ফুলে যায়। তখন `Count("reviews", distinct=True)` ব্যবহার করতে হয়।

<br>
<br>

---

<br>

### 💡 `annotate()` ও `distinct=True` আরও সহজে বোঝার বাস্তব ব্যাখ্যা (Deep Dive):

> **বাস্তব জীবনের রূপক (Analogy):**  
> মনে করুন আপনার দোকানে **১০০টি বই** আছে এবং ডাটাবেজ হলো দূরের **গোডাউন**।

#### ১. আগের কোডে কী সমস্যা হচ্ছিল?
* প্রথমে গোডাউনে গিয়ে ১০০টি বই আনলেন (`১টি কুয়েরি`)।
* এরপর প্রথম বইটি হাতে নিয়ে জিজ্ঞেস করলেন: *"এই বইয়ে কয়টা রিভিউ আছে?"* — আবার দৌড়ে গোডাউনে গেলেন (`count()`-এর কুয়েরি)।
* আবার জিজ্ঞেস করলেন: *"এই বইয়ের গড় রেটিং কত?"* — আবার দৌড়ে গোডাউনে গেলেন (`aggregate()`-এর কুয়েরি)।
* এভাবে প্রতিটা বইয়ের জন্য **২ বার করে গোডাউনে দৌড়াতে হচ্ছে**! ১০০ বইয়ের জন্য মোট: `১ + (১০০ × ২) = ২০১টি কুয়েরি`!

#### ২. সমাধান: `annotate()` কীভাবে ম্যাজিক করে?
`annotate` শব্দের সহজ অর্থ হলো—**"গায়ে বাড়তি কোনো তথ্য বা স্টিকার লাগিয়ে দেওয়া"**।

আপনি ডাটাবেজকে শুরুতেই একবার বললেন:
> *"ভাই ডাটাবেজ! তুমি ক্যালকুলেশনে অনেক ফাস্ট। আমাকে খালি বইগুলো দিও না—বইগুলো দেওয়ার সময়ই তুমি নিজে গুনে (`Count`) আর গড় বের করে (`Avg`) প্রতিটি বইয়ের গায়ে `review_count` আর `avg_rating` নামে দুটো স্টিকার লাগিয়ে একসাথে পাঠিয়ে দাও!"*

**ভেতরে কী ঘটে:**
1. **ডাটাবেজে মাত্র ১টি SQL কুয়েরি চলে:**
   ```sql
   SELECT book.*, 
          COUNT(review.id) AS review_count, 
          AVG(review.rating) AS avg_rating
   FROM book
   LEFT JOIN review ON book.id = review.book_id
   GROUP BY book.id;
   ```
2. **পাইথন অবজেক্টে কী বসে যায়:**  
   ডাটাবেজ থেকে ডেটা আসার পর প্রতিটি `book` অবজেক্টের গায়ে সরাসরি দুটো ফিল্ড যুক্ত হয়ে যায়:
   ```python
   # মেমোরিতে প্রতিটি বইয়ের চেহারা:
   book.id = 1
   book.title = "Django Guide"
   book.review_count = 15    # <--- annotate দিয়ে আসা স্টিকার!
   book.avg_rating = 4.6     # <--- annotate দিয়ে আসা স্টিকার!
   ```
3. **সিরিয়ালাইজারে সুবিধা:**  
   যেহেতু ফিল্ড দুটি বইয়ের অবজেক্টেই লেগে আছে, তাই আর `SerializerMethodField` বা কোনো মেথড কল করার দরকারই নেই! সাধারণ ফিল্ডের মতোই সিরিয়ালাইজার সরাসরি ভ্যালু পড়ে নেয়।

#### ৩. ⚠️ সেই সতর্কতা (`distinct=True`) — সংখ্যা ফুলে যায় কেন?

ধরুন **১টি বইয়ের**:
* **৩টি রিভিউ** আছে (R1, R2, R3)
* **২টি ট্যাগ** আছে (T1, T2)

এখন আপনি যদি একসাথে দুটোরই `Count` করেন:
```python
Book.objects.annotate(
    review_count=Count("reviews"),
    tag_count=Count("tags"),
)
```
ডাটাবেজ যখন `book`-এর সাথে `review` আর `tag` দুটোকেই একসাথে **SQL JOIN** করে, তখন সেগুলো গুণ হয়ে (Cartesian product) **৩ × ২ = ৬টি রো (row)** তৈরি করে ফেলে:

| Book | Review | Tag |
| :--- | :--- | :--- |
| Book 1 | R1 | T1 |
| Book 1 | R1 | T2 |
| Book 1 | R2 | T1 |
| Book 1 | R2 | T2 |
| Book 1 | R3 | T1 |
| Book 1 | R3 | T2 |

এখন আপনি `Count("reviews")` করলে ডাটাবেজ ওই ৬টা রো-ই গুনে ফেলে! তাই ৩টার জায়গায় বলবে **৬টি রিভিউ**, আর ২টার জায়গায় বলবে **৬টি ট্যাগ**!

**✅ সমাধান:**  
ডাটাবেজকে বলতে হবে *"ডুপ্লিকেট বাদ দিয়ে শুধু ইউনিকগুলো গোনো"*, অর্থাৎ `distinct=True`:
```python
Book.objects.annotate(
    review_count=Count("reviews", distinct=True),  # ✅ রেজাল্ট আসবে 3
    tag_count=Count("tags", distinct=True),        # ✅ রেজাল্ট আসবে 2
)
```

<br>

#### 🔑 এক নজরে সারসংক্ষেপ:
1. **`SerializerMethodField`-এ `.count()` বা `.aggregate()`** চালালে প্রতি অবজেক্টের জন্য নতুন কুয়েরি যায় (N+1 সমস্যা)।
2. **`annotate()`** ব্যবহার করলে ডাটাবেজ নিজেই `GROUP BY` দিয়ে একবারেই সব `Count`/`Avg`/`Sum` হিসাব করে অবজেক্টের গায়ে বসিয়ে দেয় (মাত্র **১টি কুয়েরি**)।
3. একসাথে একাধিক রিলেশনে (যেমন `reviews` ও `tags`) `Count` করলে অবশ্যই **`distinct=True`** দিতে হবে, নাহলে JOIN-এর কারণে সংখ্যা গুণ হয়ে ভুল রেজাল্ট আসবে।


<br>
<br>

---

<br>

### ❓ কেন `SerializerMethodField`-এর বদলে `IntegerField` / `FloatField` ব্যবহার করা হলো?

> **সহজ কথায় উত্তর:**  
> **"যে কাজ ডাটাবেজ নিজেই করে দিয়ে অবজেক্টের গায়ে ভ্যালু লাগিয়ে দিয়েছে, সেটার জন্য আবার আলাদা পাইথন মেথড (`SerializerMethodField`) চালানোর আর কোনো প্রয়োজনই নেই।"**

#### ১. `SerializerMethodField` আসলে কী করে এবং কখন লাগে?
`SerializerMethodField` তখন লাগে যখন কোনো ফিল্ডের মান কোনো মডেলে বা অবজেক্টে **সরাসরি উপস্থিত নেই**, বরং সেটা বের করতে আপনার **আলাদা একটি পাইথন ফাংশন (`get_<field_name>`)** লিখে হিসাব করতে হবে।

* **আগে কেন লেগেছিল?**  
  `Book` মডেলে `review_count` বা `avg_rating` নামে কোনো ফিল্ড ছিল না। তাই আপনাকে বাধ্য হয়ে ফাংশন লিখতে হয়েছিল:
  ```python
  def get_review_count(self, obj):
      return obj.reviews.count() # পাইথন ফাংশন দিয়ে জোর করে গুনে আনতে হচ্ছিল
  ```

#### ২. `annotate()` করার পর কী ঘটল?
যখন ভিউতে লিখলেন:
```python
Book.objects.annotate(
    review_count=Count("reviews"),
    avg_rating=Avg("reviews__rating"),
)
```
ডাটাবেজ নিজেই হিসাব করে `book` অবজেক্টের গায়ে সরাসরি মানগুলো বসিয়ে পাঠিয়েছে:
```python
# মেমোরিতে এখন অবজেক্টের রূপ:
book.id = 1
book.title = "Django Book"
book.review_count = 15     # <--- সরাসরি integer ভ্যালু রেডি আছে!
book.avg_rating = 4.5      # <--- সরাসরি float ভ্যালু রেডি আছে!
```

#### ৩. তাহলে কেন `IntegerField` এবং `FloatField` ব্যবহার করা হলো?
যেহেতু `book.review_count` এবং `book.avg_rating` এখন সাধারণ ফিল্ডের মতো অবজেক্টের ভেতরেই তৈরি হয়ে গেছে, তাই:
* DRF-এর সাধারণ ফিল্ড (`serializers.IntegerField`, `serializers.FloatField`) সরাসরি `obj.review_count` এবং `obj.avg_rating` পড়ে নিতে পারে।
* এর জন্য বাড়তি কোনো `get_review_count()` বা `get_avg_rating()` ফাংশন কল করতে হয় না।

#### ⚡ পারফরম্যান্সের পার্থক্য:
1. **`SerializerMethodField`:** প্রতিটা অবজেক্টের জন্য পাইথনের একটি মেথড ফ্রেম ওপেন করে এবং ফাংশন কল করে, যা পাইথনে সামান্য স্লো।
2. **`IntegerField` / `FloatField`:** সরাসরি অবজেক্টের অ্যাট্রিবিউট থেকে ডেটা নেয় (ডিরেক্ট অ্যাট্রিবিউট লুকআপ), যা অনেক বেশি দ্রুত এবং কোড অনেক ক্লিন রাখে।

#### 📌 সংক্ষেপে:
* **মান নিজে হিসাব করতে হলে** ➡️ `SerializerMethodField` (ফাংশন দরকার)।
* **মান আগে থেকেই অবজেক্টে উপস্থিত থাকলে** (যেমন `annotate` দিয়ে আনা সংখ্যা) ➡️ সাধারণ `IntegerField`/`FloatField` (সরাসরি ফিল্ড রিড করে)।


<br>
<br>

---

<br>

### 🔢 `Count` এবং `Avg` এর কাজ কী? (সহজ ব্যাখ্যা)

Django ORM-এ `Count` এবং `Avg` হলো **অ্যাগ্রিগেট ফাংশন (Aggregate Functions)**। এগুলো ডাটাবেজে একাধিক রো (rows) নিয়ে হিসাব-নিকাশ করে **একটি মাত্র ফলাফল** তৈরি করে দেয়।

---

#### ১. `Count` এর কাজ: "মোট সংখ্যা বা কয়টা আছে তা গোনা"
* **সহজ অর্থ:** কোনো কিছুর **মোট সংখ্যা** (Quantity) বের করা।
* **বাস্তব উদাহরণ:** একটা বইয়ে মোট কয়জন পাঠক রিভিউ দিয়েছে?
  * রিভিউ ১: ★★★★★
  * রিভিউ ২: ★★★★☆
  * রিভিউ ৩: ★★★☆☆
  * 👉 মোট রিভিউ কয়টি? **৩টি**। এই "৩" সংখ্যাটি বের করাই হলো `Count` এর কাজ।
* **কোড:**
  ```python
  Count("reviews")  # SQL: COUNT(review.id)
  ```

---

#### ২. `Avg` এর কাজ: "গড় মান (Average) বের করা"
* **সহজ অর্থ:** কোনো নির্দিষ্ট সংখ্যার কলামের সব মান যোগ করে মোট সংখ্যা দিয়ে ভাগ করে **গড় (Average)** বের করা।
* **বাস্তব উদাহরণ:** ওই ৩ জন পাঠকের দেওয়া রেটিংয়ের গড় কত?
  * পাঠক ১ দিয়েছে: ৫ স্টার
  * পাঠক ২ দিয়েছে: ৪ স্টার
  * পাঠক ৩ দিয়েছে: ৩ স্টার
  * 👉 যোগফল = ৫ + ৪ + ৩ = ১২
  * 👉 গড় = ১২ ÷ ৩ = **৪.০**
  * এই **৪.০** গড় রেটিং বের করার কাজটিই করে `Avg`।
* **কোড:**
  ```python
  Avg("reviews__rating")  # SQL: AVG(review.rating)
  # লক্ষ্য করুন: reviews__rating মানে reviews টেবিলের rating কলামের গড় করো
  ```

---

#### 💡 সংক্ষেপে পার্থক্য:

| ফাংশন | কী করে? | বাস্তব উদাহরণ | রিটার্ন টাইপ |
| :--- | :--- | :--- | :--- |
| **`Count`** | **কয়টা আছে গুনে বলে** | এই বইয়ে মোট ১৫টি রিভিউ আছে | পূর্ণসংখ্যা (Integer) যেমন: `15` |
| **`Avg`** | **গড় কত তা বের করে** | এই বইয়ের রিভিউগুলোর গড় রেটিং ৪.৩ | দশমিক সংখ্যা (Float) যেমন: `4.3` |


<br>
<br>

---

<br>

### 🧭 কখন `select_related`, কখন `prefetch_related`, আর কখন `annotate` ব্যবহার করবেন? (Ultimate Cheat Sheet)

সবসময় নিজেকে একটি মাত্র প্রশ্ন করবেন:  
👉 **"আমি কি পুরো ডেটা/অবজেক্ট চাই, নাকি শুধু একটা হিসাব করা সংখ্যা/রেজাল্ট চাই?"**

---

#### ১. যখন `select_related` ব্যবহার করবেন:
* **চাহিদা:** অন্য টেবিলের **১টি মাত্র অবজেক্টের ডেটা** দরকার (যেমন: বইয়ের লেখকের নাম, বইয়ের ক্যাটাগরির নাম)।
* **চেনার উপায়:** `ForeignKey` বা `OneToOneField` ধরে যাচ্ছেন এবং আপনার পুরো অবজেক্ট বা তার সাধারণ ফিল্ড দরকার (`book.author.name`)।

#### ২. যখন `prefetch_related` ব্যবহার করবেন:
* **চাহিদা:** অন্য টেবিলের **একাধিক অবজেক্টের লিস্ট** দরকার (যেমন: বইয়ের সব ট্যাগের নাম, বা বইয়ের সব রিভিউয়ের বিস্তারিত লেখা)।
* **চেনার উপায়:** রেসপন্সে আপনার একটা **লিস্ট/অ্যারে** দেখাতে হবে (যেমন: `tags: ["Django", "Python"]` বা `reviews: [{"rating": 5, "text": "..."}, ...]`)।

#### ৩. যখন `annotate` ব্যবহার করবেন:
* **চাহিদা:** অন্য টেবিলের পুরো ডেটা বা অবজেক্টের লিস্ট আপনার **দরকার নেই**! আপনার শুধু একটি **হিসাব করা মান (Calculated Value / Summary)** দরকার।
* **চেনার উপায়:** প্রশ্নটা যদি এমন হয়—
  * *মোট কয়টা আছে?* ➡️ `Count`
  * *গড় কত?* ➡️ `Avg`
  * *মোট দাম বা যোগফল কত?* ➡️ `Sum`
  * *সবচেয়ে বড় বা ছোট মান কত?* ➡️ `Max` / `Min`
  * *কোনো রেকর্ড বিদ্যমান আছে কি না (True/False)?* ➡️ `Exists`

---

#### 📊 বাস্তব উদাহরণ দিয়ে পার্থক্য:

ধরুন আপনি `Book` লিস্ট API বানাচ্ছেন:

| আপনার API রেসপন্সে যা দেখাতে চান | কী ব্যবহার করবেন? | কেন? |
| :--- | :--- | :--- |
| `"author_name": "Humayun Ahmed"` | **`select_related`** | ১ জন লেখকের ডেটা আনতে হবে (Single Object) |
| `"reviews": [{"rating": 5}, {"rating": 4}]` | **`prefetch_related`** | সব রিভিউ অবজেক্টের **লিস্ট** দেখাতে হবে |
| `"review_count": 15` | **`annotate`** | রিভিউয়ের লিস্ট দরকার নেই, শুধু **সংখ্যাটা** দরকার! |
| `"avg_rating": 4.5` | **`annotate`** | রিভিউয়ের লিস্ট দরকার নেই, শুধু **গড়** দরকার! |
| `"total_sales": 50000` | **`annotate`** | সব অর্ডারের লিস্ট দরকার নেই, শুধু **যোগফল (`Sum`)** দরকার! |

---

#### ⚠️ যে ভুলটি অনেকেই করে (কখন `prefetch_related` ব্যবহার করবেন না):
ধরুন আপনার শুধুমাত্র `review_count` দরকার। আপনি যদি `prefetch_related("reviews")` করে তারপর পাইথনে `len(obj.reviews.all())` লেখেন:
* ডাটাবেজ থেকে **হাজার হাজার রিভিউয়ের পুরো ডেটা** মেমোরিতে (RAM) চলে আসবে শুধু সংখ্যাটা গোনার জন্য! এতে RAM নষ্ট হবে এবং সার্ভার স্লো হয়ে যাবে।
* অথচ `annotate(review_count=Count("reviews"))` করলে ডাটাবেজ নিজেই ক্যালকুলেশন করে শুধু একটি সংখ্যা (`15`) পাঠাবে—মেমোরি একদম ফাঁকা ও ফাস্ট থাকবে!

---

#### 🔑 এক লাইনে মনে রাখার গোল্ডেন রুল:
* **১টা অবজেক্ট লাগলে** ➡️ `select_related`
* **অনেকগুলো অবজেক্টের লিস্ট লাগলে** ➡️ `prefetch_related`
* **অবজেক্ট না, শুধু হিসাব (Count / Avg / Sum / Max / Min) লাগলে** ➡️ `annotate`


<br>
<br>

---

<br>
<br>

## উদাহরণ ৭ (Advanced): নেস্টেড serializer (`Order` → `items` → `book` → `author`)

<br>

### ❌ আগে

```python
class OrderItemSerializer(serializers.ModelSerializer):
    book_title = serializers.CharField(source="book.title")
    author = serializers.CharField(source="book.author.name")

    class Meta:
        model = OrderItem
        fields = ["book_title", "author", "quantity"]

class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True)
    user_email = serializers.CharField(source="user.email")

    class Meta:
        model = Order
        fields = ["id", "user_email", "items"]

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Order.objects.all()    # ❌ user, items, book, author সব N+1
    serializer_class = OrderSerializer
```

> **কী হচ্ছে:** ২০টি অর্ডার এবং প্রতিটিতে ৫টি করে আইটেম থাকলে (মোট ১০০টি আইটেম):
> * মূল অর্ডার আনতে: **১টি** কুয়েরি (`SELECT * FROM order`)
> * প্রতি অর্ডারের `user_email` আনতে: **২০টি** কুয়েরি
> * প্রতি অর্ডারের `items` আনতে: **২০টি** কুয়েরি
> * ১০০টি আইটেমের প্রতিটির জন্য `book` আনতে: **১০০টি** কুয়েরি
> * ১০০টি বইয়ের প্রতিটির `author` আনতে: **১০০টি** কুয়েরি
> * **সর্বমোট: ১ + ২০ + ২০ + ১০০ + ১০০ = ২৪১টি কুয়েরি!** (ভয়াবহ নেস্টেড N+1 বিস্ফোরণ)।

<br>

### ✅ পরে

```python
from django.db.models import Prefetch

class OrderViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = (
        Order.objects
        .select_related("user")                       # Order → User (FK)
        .prefetch_related(
            Prefetch(
                "items",
                queryset=OrderItem.objects.select_related("book__author"),  # ✅ ভেতরে JOIN
            )
        )
    )
    serializer_class = OrderSerializer
```

**কী হচ্ছে:** ২৪১টি কুয়েরি কমে মাত্র **২টি SQL কুয়েরিতে** নেমে আসে!

<br>
<br>

---

<br>

### 💡 নেস্টেড সিরিয়ালাইজার অপটিমাইজেশন — সহজ বাংলায় ব্যাখ্যা (Deep Dive):

এটি রিয়েল-ওয়ার্ল্ড ই-কমার্স প্রজেক্টে সবচেয়ে বেশি দেখা যায়! চলুন ধাপে ধাপে রাস্তাটা (Relationship Chain) বুঝি:

```text
Order ──(ForeignKey / ১ জন)──▶ User
  │
  └──(One-to-Many / অনেকগুলো)──▶ OrderItem ──(FK / ১টা)──▶ Book ──(FK / ১ জন)──▶ Author
```

#### ১. প্রথম ধাপ: `Order` থেকে `User` (১ নম্বর কুয়েরি)
* ১টি অর্ডার করেন মাত্র **১ জন ইউজার** (`ForeignKey`)।
* তাই সরাসরি **`.select_related("user")`** ব্যবহার করা হলো।
* এর ফলে প্রথম কুয়েরিতেই `Order` আর `User` টেবিল `JOIN` হয়ে একবারে চলে আসে:
  ```sql
  -- ১ নম্বর কুয়েরি: সব Order + তাদের User একসাথে
  SELECT order.*, user.*
  FROM order
  INNER JOIN user ON order.user_id = user.id;
  ```

#### ২. দ্বিতীয় ধাপ: `Order` থেকে `items` → `book` → `author` (২ নম্বর কুয়েরি)
* ১টি অর্ডারে **একাধিক আইটেম** থাকে (`One-to-Many`), তাই এখানে `select_related` চলবে না—লাগবে **`prefetch_related`**।
* **ম্যাজিক ট্রিক (`Prefetch` এর ভেতর `select_related`):**  
  আমরা যদি শুধু `prefetch_related("items")` লিখতাম, তবে `items` আসতো ঠিকই, কিন্তু প্রতিটি আইটেমের ভেতর গিয়ে `book` আর `author` আনতে গিয়ে আবার ۲۰۰টি কুয়েরি হতো!
* তাই আমরা **`Prefetch("items", queryset=OrderItem.objects.select_related("book__author"))`** লিখে জ্যাঙ্গোকে বলে দিলাম:
  > *"ভাই জ্যাঙ্গো! তুমি যখন `OrderItem` গুলো আনতে ডাটাবেজে যাবে, তখন খালি `OrderItem` এনো না—ওই একই কুয়েরির ভেতর `book` আর `author`-কেও `JOIN` করে একসাথে নিয়ে এসো!"*
* এর ফলে ২য় কুয়েরিটি চলে ঠিক এভাবে:
  ```sql
  -- ২ নম্বর কুয়েরি: সব OrderItem + তাদের Book + Author একসাথে JOIN হয়ে আসে!
  SELECT order_item.*, book.*, author.*
  FROM order_item
  INNER JOIN book ON order_item.book_id = book.id
  INNER JOIN author ON book.author_id = author.id
  WHERE order_item.order_id IN (1, 2, 3, ..., 20);
  ```

#### ৩. লক্ষ্য করুন: এখানে কেন `to_attr` লাগেনি?
* উদাহরণ ৫-এ আমরা `.filter(is_approved=True)` করে আংশিক ডেটা এনেছিলাম, তাই আলাদা নাম (`to_attr`) দিতে হয়েছিল।
* কিন্তু এখানে আমরা অর্ডারের **সবগুলো `items`**-ই আনছি, শুধু তাদের সাথে `book__author` জুড়ে দিচ্ছি।
* তাই `to_attr` না দিলে জ্যাঙ্গো ডিফল্টভাবে `order.items.all()` ক্যাশেই সাজিয়ে রাখে, আর `OrderSerializer`-এর `items = OrderItemSerializer(many=True)` সরাসরি ওই ক্যাশ থেকেই সব ডেটা পড়ে নেয়!

#### 🔑 এক নজরে মনে রাখার কৌশল:
* **নেস্টেড রিলেশন থাকলে (One-to-Many এর ভেতর আবার ForeignKey):**  
  বাইরে **`prefetch_related(Prefetch(...))`** আর ভেতরের `queryset`-এ **`select_related(...)`** ব্যবহার করুন।
* *বিকল্প শর্টকাট:* একই কাজ `.prefetch_related("items__book__author")` দিয়েও করা যায়, তবে সেক্ষেত্রে ৩-৪টি আলাদা কুয়েরি চলে। আর `Prefetch(..., queryset=OrderItem.objects.select_related("book__author"))` ব্যবহার করলে **মাত্র ২টি কুয়েরিতেই** কাজ শেষ হয়—তাই এটি সবচেয়ে বেশি অপটিমাইজড!


<br>
<br>

---

<br>
<br>

## উদাহরণ ৮ (Advanced): Model `@property` এর ভেতরে লুকানো N+1

<br>

### ❌ আগে

```python
# models.py
class Book(models.Model):
    ...
    @property
    def top_reviews(self):
        return self.reviews.filter(rating__gte=4)     # ❌ প্রতিবার নতুন query

    @property
    def is_popular(self):
        return self.reviews.count() > 10              # ❌ আরেকটা query

# serializers.py
class BookSerializer(serializers.ModelSerializer):
    is_popular = serializers.BooleanField(read_only=True)

    class Meta:
        model = Book
        fields = ["id", "title", "is_popular"]
```

> **কী হচ্ছে:** `@property` দেখতে একদম সাধারণ ফিল্ড বা অ্যাট্রিবিউটের মতো (`book.is_popular`)। তাই কোড রিভিউয়ের সময় এর ভেতরে লুকিয়ে থাকা ডাটাবেজ কুয়েরি সহজে চোখে পড়ে না! সিরিয়ালাইজারে `is_popular` পড়লেই প্রতি বইয়ের জন্য আলাদা করে `SELECT COUNT(*) FROM review WHERE book_id = ?` চলতে থাকে (১০০ বইয়ে ১০১ কুয়েরি)।

<br>

### ✅ পরে

```python
# models.py
class Book(models.Model):
    ...
    @property
    def is_popular(self):
        # ✅ ১ম চেক: annotate করা থাকলে সরাসরি সেটাই ব্যবহার করো (সবচেয়ে ফাস্ট)
        if hasattr(self, "_review_count"):
            return self._review_count > 10
        # ✅ ২য় চেক (Fallback): prefetch cache ব্যবহার হবে (len + .all() — .count()/.filter() নয়)
        return len(self.reviews.all()) > 10

# views.py
class BookViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Book.objects.annotate(_review_count=Count("reviews"))
    serializer_class = BookSerializer
```

**কী হচ্ছে:** `is_popular` প্রপার্টিটা এখন স্মার্ট! এটি প্রথমে দেখে ভিউ থেকে `annotate` করে মান পাঠানো হয়েছে কি না। পাঠালে ১টি কুয়েরিতেই কাজ শেষ। আর যদি কোনো ভিউতে `annotate` না করে `prefetch_related("reviews")` করা থাকে, তবে `len(self.reviews.all())` ক্যাশ থেকে ডেটা নিয়ে নেয়—কোনো বাড়তি কুয়েরি চলে না!

<br>
<br>

---

<br>

### 💡 `@property` এর লুকানো N+1 এবং সমাধান — সহজ বাংলায় ব্যাখ্যা (Deep Dive):

#### ১. `@property` কেন বিপজ্জনক (Silent Killer)?
* সাধারণত `book.title` বা `book.price` দেখলে আমরা ভাবি এটা শুধু মেমোরি থেকে সাধারণ একটা ভ্যালু পড়ছে।
* কিন্তু `book.is_popular` দেখতে সাধারণ ফিল্ডের মতো হলেও, এর পেছনে `@property` দিয়ে `self.reviews.count()` লেখা আছে—যা গোপনে ডাটাবেজে কুয়েরি পাঠায়!
* ফলে ডেভেলপার সিরিয়ালাইজারে `fields = ["id", "title", "is_popular"]` লিখে নিশ্চিন্তে বসে থাকেন, আর পেছনে চুপিচুপি ১০০+ কুয়েরি চলতে থাকে!

#### ২. `hasattr(self, "_review_count")` কীভাবে কাজ করছে?
* **`hasattr(obj, "নাম")`** পাইথনের একটি বিল্ট-ইন ফাংশন, যা চেক করে এই অবজেক্টের ভেতর ওই নামের কোনো অ্যাট্রিবিউট বা ভেরিয়েবল আছে কি না (`True` বা `False` দেয়)।
* আপনি যখন `BookViewSet`-এ লিখলেন:
  ```python
  Book.objects.annotate(_review_count=Count("reviews"))
  ```
  তখন ডাটাবেজ প্রতিটি `book` অবজেক্টের গায়ে `_review_count` নামে সংখ্যাটি (যেমন `15`) বসিয়ে দেয়।
* এরপর যখন `book.is_popular` কল হয়:
  1. প্রথমে চেক করে: `hasattr(self, "_review_count")` — অর্থাৎ, *"আমার গায়ে কি `annotate` দিয়ে আনা `_review_count` স্টিকার লাগানো আছে?"*
  2. যদি থাকে (`True`), তাহলে ডাটাবেজে না গিয়ে সরাসরি `15 > 10` চেক করে `True` রিটার্ন করে দেয়! (**০টি বাড়তি কুয়েরি!**)

#### ৩. Fallback হিসেবে `self.reviews.count()` এর বদলে `len(self.reviews.all())` কেন লেখা হলো?
এটি Django ORM-এর অত্যন্ত গুরুত্বপূর্ণ একটি নিয়ম! ধরুন অন্য কোনো ভিউতে আপনি `annotate` করেননি, বরং `Book.objects.prefetch_related("reviews")` করেছেন:
* যদি লিখতেন `self.reviews.count()` ➡️ জ্যাঙ্গো prefetch ক্যাশ **ব্যবহার করবে না**, সরাসরি ডাটাবেজে নতুন `COUNT(*)` কুয়েরি চালাবে!
* যদি লেখেন `len(self.reviews.all())` ➡️ `.all()` সরাসরি মেমোরির **prefetch ক্যাশ** থেকে লিস্টটা নেয় এবং `len()` পাইথনে সেই লিস্টের দৈর্ঘ্য গুনে বলে দেয় (**কোনো নতুন SQL কুয়েরি চলে না**)!

#### 🔑 গোল্ডেন রুল (ক্যাশ বনাম নতুন কুয়েরি):

| যেগুলো Prefetch Cache ব্যবহার করে (✅ ফাস্ট) | যেগুলো সবসময় নতুন SQL Query চালায় (❌ N+1) |
| :--- | :--- |
| `.all()` | `.filter(...)` / `.exclude(...)` |
| `len(obj.relation.all())` | `.count()` |
| লুপের ভেতর `if obj.relation.all():` | `.exists()` |
| `list(obj.relation.all())[0]` | `.first()` / `.last()` |

*(সতর্কতা: তবে `prefetch_related` না করে থাকলে `len(self.reviews.all())` সব রো মেমোরিতে লোড করে ফেলবে, তাই লিস্ট ভিউতে সবসময় `annotate` অথবা `prefetch_related` ব্যবহার করতে হবে!)*
