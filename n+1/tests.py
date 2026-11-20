#N+1 ধরার উপায়
#tests.py file 

# tests.py
from django.test import TestCase

class BookQueryTest(TestCase):
    def test_book_list_query_count(self):
        # ... ডেটা তৈরি ...
        with self.assertNumQueries(1):   # ১ এর বেশি হলে টেস্ট ফেল
            self.client.get("/api/books/")

#আরেকটা উপায় হলো django-debug-toolbar এর SQL প্যানেল, যেটা duplicate query হাইলাইট করে।