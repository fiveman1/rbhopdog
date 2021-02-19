class Node:
    def __init__(self, name, ID, left = None, right = None):
        self.name = name
        self.ID = ID
        self.left = left
        self.right = right
        self.height = 1
    def __gt__(self, other):
        return isinstance(other, Node) and self.name > other.name

class MapTree:
    def __init__(self):
        self.root = None

    def get(self, name):
        name = name.lower()
        current = self.root
        while current != None:
            if current.name.startswith(name):
                return current.ID
            elif name > current.name:
                current = current.right
            else:
                current = current.left
        return -1

    def add(self, name, ID):
        node = Node(name.lower(), ID)
        if not self.root:
            self.root = node
            return
        self.insert(self.root, node)

    # AVL tree insertion
    # adapted from https://www.geeksforgeeks.org/avl-tree-set-1-insertion/
    def insert(self, root, node):
        # Step 1 - Perform normal BST
        if not root:
            return node
        elif node < root:
            root.left = self.insert(root.left, node)
        else:
            root.right = self.insert(root.right, node)
 
        # Step 2 - Update the height of the 
        # ancestor node
        root.height = 1 + max(self.getHeight(root.left),
                           self.getHeight(root.right))
 
        # Step 3 - Get the balance factor
        balance = self.getBalance(root)
 
        # Step 4 - If the node is unbalanced, 
        # then try out the 4 cases
        # Case 1 - Left Left
        if balance > 1 and node < root.left:
            return self.rightRotate(root)
 
        # Case 2 - Right Right
        if balance < -1 and node > root.right:
            return self.leftRotate(root)
 
        # Case 3 - Left Right
        if balance > 1 and node > root.left:
            root.left = self.leftRotate(root.left)
            return self.rightRotate(root)
 
        # Case 4 - Right Left
        if balance < -1 and node < root.right:
            root.right = self.rightRotate(root.right)
            return self.leftRotate(root)
 
        return root
 
    def leftRotate(self, z):
 
        y = z.right
        T2 = y.left
 
        # Perform rotation
        y.left = z
        z.right = T2
 
        # Update heights
        z.height = 1 + max(self.getHeight(z.left),
                         self.getHeight(z.right))
        y.height = 1 + max(self.getHeight(y.left),
                         self.getHeight(y.right))
 
        # Return the new root
        return y
 
    def rightRotate(self, z):
 
        y = z.left
        T3 = y.right
 
        # Perform rotation
        y.right = z
        z.left = T3
 
        # Update heights
        z.height = 1 + max(self.getHeight(z.left),
                        self.getHeight(z.right))
        y.height = 1 + max(self.getHeight(y.left),
                        self.getHeight(y.right))
 
        # Return the new root
        return y
 
    def getHeight(self, root):
        if not root:
            return 0
        return root.height
 
    def getBalance(self, root):
        if not root:
            return 0
        return self.getHeight(root.left) - self.getHeight(root.right)

    def print(self):
        self.preOrder(self.root)
 
    def preOrder(self, root):
        if not root:
            return
        print("{0} ".format(root.name), end="")
        self.preOrder(root.left)
        self.preOrder(root.right)