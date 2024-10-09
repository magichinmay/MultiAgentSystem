from collections import deque

# Create a deque
my_deque = deque([1, 2, 3, 4, 5])
for i in range(4):
    # Pop the first element
    first_element=my_deque.popleft()

    # Output the popped element and the remaining deque
    print(f"Popped element: {first_element}")
    print(f"Remaining deque: {my_deque}")
