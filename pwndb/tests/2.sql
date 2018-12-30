create table foo(a,b,c);
insert into foo (a,b,c) values ('1"',"1","1"), ("2","2","2"), ("3","3","3");
select * from foo;
get cursor 0;
update cursor 0 set b="TEST";
select * from foo;
get cursor 1;
