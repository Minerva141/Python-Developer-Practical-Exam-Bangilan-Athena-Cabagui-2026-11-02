# Ordered Car List (Django)

A web page for storing and managing (CRUD) an **ordered list of 100,000 cars** in a relational
database. Cars can be filtered by colour and are always returned in list order, and a car can be
moved by updating **one database row**.

Stack: Python 3, Django, SQLite3, Bootstrap 5, jQuery / jQuery UI (loaded from CDNs).

## Setup

**Requirements:** Python 3 (tested on Python 3.13 with Django 6.1) and pip. No separate database server is
needed: the project uses SQLite3, which comes with Python.

1. **Get the code**

       git clone <repository-url>
       cd <repository-folder>          # the folder that contains manage.py

2. **(Recommended) create a virtual environment**

       # Windows (PowerShell)
       python -m venv .venv
       .venv\Scripts\Activate.ps1

       # macOS / Linux
       python3 -m venv .venv
       source .venv/bin/activate

3. **Install dependencies**

       pip install -r requirements.txt

4. **Create the database tables**

       python manage.py migrate

5. **Load the sample data (100,000 cars)**

       python manage.py seed_cars

   `db.sqlite3` is included in the repository already seeded, so this step is only needed to reset the
   data or if the file is missing. It takes a few seconds.

6. **Run the site**

       python manage.py runserver

   Open http://127.0.0.1:8000/ in your browser. Stop the server with Ctrl+C.

7. **Run the tests** (in a second terminal, or after stopping the server)

       python manage.py test

**Troubleshooting**
- `No module named django`: activate the virtual environment and run `pip install -r requirements.txt` again.
- `python` is not recognised: install Python from python.org and tick "Add Python to PATH" (or use `py` on Windows).
- The page looks unstyled or drag-and-drop does not work: the page loads Bootstrap and jQuery from CDNs, so it
  needs an internet connection.
- The terminal seems stuck: it is running the server. Press Ctrl+C, or open a second terminal for other commands.

## What it does
- Lists all cars in order, 50 per page, with the number of cars per colour.
- **Show <colour> cars** returns only that colour, still in list order.
- **Move** a car by dragging its ☰ handle. Only that car's row is updated.
- **Add** (appended at the end of the list), **Edit** and **Delete** (Bootstrap pop-ups). After saving
  or deleting you return to the same page, filter and search.
- **Search** by name, combinable with the colour filter.

## Schema (also in `schema.sql`)
    cars_car(
      id        integer primary key,
      name      varchar(100) not null,
      color     varchar(30)  not null,   -- stored lowercase
      position  bigint       not null    -- list order
    )
    INDEX car_color_pos_idx (color, position)   -- "show blue cars", already in order, no sort step
    INDEX car_pos_idx (position)                -- full ordered list and neighbour lookups

## Design: gapped positions
The list order is simply `ORDER BY position, id`. Positions are spaced `GAP = 2**20` apart, so there
is always room between two neighbours.

To move a car in front of another, the car is given a position halfway between its new neighbours:

    before:  D=1  B=2  E=3  C=4  A=5            (illustration with small numbers)
    move C in front of B  ->  C = (1 + 2) / 2   ->  order D C B E A   (1 row changed)
    move D in front of A  ->  D = (3 + 5) / 2   ->  blue cars: E D A  (1 row changed)

So a move costs one `UPDATE` on one row, whether the list has 100,000 cars or 10 million. If two
neighbours ever become adjacent (no whole number left between them), all rows are renumbered with
fresh gaps in one transaction. That is O(n) but rare: a single spot can be halved about 20 times
before it happens.

Filtering by colour keeps the global order because the `(color, position)` index is already sorted
by position within each colour.

## Project layout
    config/                      Django settings and root URLs
    cars/models.py               Car model, indexes, move_before / move_after / rebalance
    cars/views.py                list (filter, search, pagination), create, edit, delete, move (AJAX)
    cars/urls.py                 URL routes
    cars/forms.py                add/edit form
    cars/templates/cars/         base.html, car_list.html (modals + drag-and-drop JS), car_form.html
    cars/management/commands/    seed_cars.py (creates the 100,000 sample cars)
    cars/tests.py                automated tests, including the exam's example and "a move updates one row"
    schema.sql                   the table and index definitions

## Decisions, assumptions and trade-offs
- **Gapped integers vs alternatives.** A dense 1..N index makes a move update up to N rows. A linked list
  needs several updates per move and awkward recursive queries to read the order back. Gapped positions
  give one-row moves and plain indexed reads.
- **Pagination (50 per page)** because rendering 100,000 rows is impractical. Drag-and-drop works within
  the visible page. Very high page numbers use `OFFSET`, which slows down; keyset pagination would fix that.
- **Moves in a filtered view** are relative to a neighbouring car, so they stay consistent with the global order.
- **New cars** are appended at the end and can be dragged to where they belong.
- **Colour** is a normalised lowercase string. With many colours a separate Colour table would be cleaner.
- **Search** is a case-insensitive "contains" match on the name, ranked: exact name, then starts-with,
  then contains (each group keeps list order). It scans all rows (about tens of milliseconds at
  100,000 cars). For much larger data I would use a "starts with" search on an index or full-text search.
  While searching, results are ordered by relevance, so a drag places the car next to the one it is
  dropped on, in the global order. The colour buttons without a search show the pure list order.
- **Concurrency.** Two simultaneous moves into the same slot could produce equal positions; ties break by
  id, so the order stays deterministic. `select_for_update` could be added for strict guarantees.
- **Numbered names.** The demo data uses Car 1 ... Car 100000 because letters only work for a handful of cars.
  The exam's D, B, E, C, A example is covered by the tests.
- **CDNs.** Bootstrap and jQuery load from the internet, so the page needs a connection to look right.
- **Database.** SQLite3 for easy setup. Nothing in the code is SQLite-specific, so PostgreSQL or MySQL
  would only need a change in `DATABASES`.

## Tests
`python manage.py test` runs the automated tests: the exam's example (D, B, E, C, A with blue = D, E, A), the claim that
a move changes exactly one row, gap exhaustion and rebalancing, CRUD views, colour filtering, search ranking,
pagination links that keep filters, and safe return-to-page redirects.