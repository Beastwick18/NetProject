To run this program, you must have python3 installed on your system.
The command to run the program for one router instance is:
    python3 router.py <PORT> <ROUTER ID>
where port is the port number for this particular router and router
id is the letter associated with the router in the config file.
Note that the port number must be continuous starting from the first
router, A. This means that if router A is given a port of 12000, then
B must have a port of 12001, C must have a port of 12002, and so on.

For this program to work, there must be one instance of each router
running. So multiple terminals should be opened running an instance
of router.py for each router in the config file.

To exit the program at any time, Ctrl+C will exit and properly close
all ports and sockets.

The algorithm for the bellman ford method in the router.py file is
provided by the website:
    https://en.wikipedia.org/wiki/Bellman%E2%80%93Ford_algorithm
