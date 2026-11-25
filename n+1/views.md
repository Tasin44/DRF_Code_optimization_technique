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

