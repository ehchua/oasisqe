
The dbchange branch is for converting OASIS to use the SQLAlchemy database ORM. Until
now, OASIS just had hard-coded SQL. (When it was originally written, there were no ORMs)

This is a huge change, but due to some bugs and inconsistencies discovered around the
way it handles database transactions, it was decided that it was time to do this.

This branch may often not even run. Once the changes are complete and reasonably well
tested, it'll be merged back into master.


- Colin
