# Surgical Changes Anti-Pattern

> **When asked to fix a bug, fix the bug. Don't repaint the house while you're at it.**

LLMs struggle with scope discipline. When editing a file, they often "improve" adjacent code — reformatting, renaming variables, adding documentation, or refactoring patterns they find unsatisfying. This creates noisy diffs, introduces risk in untested areas, and makes code review painful.

---

## Example 1: Adjacent Code "Improvements"

**User request:** *"Fix the null pointer exception in the `processOrder` method"*

### ❌ What LLMs Do (Touch Everything)

```diff
  public class OrderService {
-     // process the order
-     public void processOrder(Order order) {
+     /**
+      * Processes an order by validating, calculating totals,
+      * and persisting to the database.
+      *
+      * @param order the order to process
+      * @throws IllegalArgumentException if order is null
+      */
+     public void processOrder(@NonNull Order order) {
+         Objects.requireNonNull(order, "Order cannot be null");
          if (order.getItems() == null) {
-             order.setItems(new ArrayList<>());
+             order.setItems(Collections.emptyList());
          }
-         double total = 0;
-         for (OrderItem item : order.getItems()) {
-             total += item.getPrice() * item.getQuantity();
-         }
-         order.setTotal(total);
+         double total = order.getItems().stream()
+                 .mapToDouble(item -> item.getPrice() * item.getQuantity())
+                 .sum();
+         order.setTotal(total);
          orderRepository.save(order);
      }
  
-     public List<Order> getOrders(int userId) {
-         return orderRepository.findByUserId(userId);
+     public List<Order> getOrdersByUserId(final int userId) {
+         return orderRepository.findByUserId(userId);
      }
  }
```

**Problems (7 unrequested changes):**
1. Added Javadoc to a method that wasn't part of the task
2. Added `@NonNull` annotation — not the bug
3. Added `Objects.requireNonNull` — not the bug
4. Changed `ArrayList<>()` to `Collections.emptyList()` — not the bug
5. Refactored for-loop to streams — not the bug
6. Renamed `getOrders` to `getOrdersByUserId` — different method entirely
7. Added `final` keyword to parameter — different method entirely

### ✅ What Should Happen (Fix Only the Bug)

```diff
  public class OrderService {
-     // process the order
      public void processOrder(Order order) {
+         if (order == null) {
+             return;
+         }
          if (order.getItems() == null) {
              order.setItems(new ArrayList<>());
          }
```

**That's it.** The null pointer was caused by `order` being null. Add a null check. Done.

If the agent notices that the for-loop could be a stream, or that `getOrders` has a poor name, it should **mention it**:

```
Note: I noticed `getOrders` could be renamed to `getOrdersByUserId` for 
clarity, and the for-loop in processOrder could use Java streams. 
These are unrelated to the bug fix — want me to address them separately?
```

---

## Example 2: Unsolicited Refactoring

**User request:** *"Add a `phoneNumber` field to the User model"*

### ❌ What LLMs Do (Refactor While Adding)

**Python:**
```diff
- class User:
-     def __init__(self, name, email):
-         self.name = name
-         self.email = email
-     
-     def to_dict(self):
-         return {"name": self.name, "email": self.email}

+ from dataclasses import dataclass, field, asdict
+ from typing import Optional
+ import re
+ 
+ @dataclass
+ class User:
+     name: str
+     email: str
+     phone_number: Optional[str] = None
+     
+     def __post_init__(self):
+         if self.phone_number and not re.match(r'^\+?[\d\s-]+$', self.phone_number):
+             raise ValueError(f"Invalid phone number: {self.phone_number}")
+     
+     def to_dict(self) -> dict:
+         return asdict(self)
```

**Java:**
```diff
- public class User {
-     private String name;
-     private String email;
-     
-     public User(String name, String email) {
-         this.name = name;
-         this.email = email;
-     }
-     // getters and setters...
- }

+ @Data
+ @Builder
+ @NoArgsConstructor
+ @AllArgsConstructor
+ public class User {
+     private String name;
+     
+     @Email
+     private String email;
+     
+     @Pattern(regexp = "^\\+?[\\d\\s-]+$")
+     private String phoneNumber;
+ }
```

**Unrequested changes:**
- Migrated from plain class to dataclass/Lombok
- Added phone number validation — nobody asked for validation
- Added `@Email` annotation on existing field — not part of the task
- Changed constructor pattern — breaks existing callers
- Added Builder pattern — not the task

### ✅ What Should Happen (Add the Field, Nothing Else)

**Python:**
```diff
  class User:
-     def __init__(self, name, email):
+     def __init__(self, name, email, phone_number=None):
          self.name = name
          self.email = email
+         self.phone_number = phone_number
      
      def to_dict(self):
-         return {"name": self.name, "email": self.email}
+         return {"name": self.name, "email": self.email, "phone_number": self.phone_number}
```

**Java:**
```diff
  public class User {
      private String name;
      private String email;
+     private String phoneNumber;
      
-     public User(String name, String email) {
+     public User(String name, String email, String phoneNumber) {
          this.name = name;
          this.email = email;
+         this.phoneNumber = phoneNumber;
      }
+     
+     public String getPhoneNumber() { return phoneNumber; }
+     public void setPhoneNumber(String phoneNumber) { this.phoneNumber = phoneNumber; }
      // existing getters and setters...
  }
```

Match the existing style. Add the field. Update serialization. Done.

---

> **Key Takeaway:** Scope discipline is the mark of a professional. When the task is "add a field," add a field. When the task is "fix a bug," fix the bug. Improvements to adjacent code should be **suggested in comments**, not silently applied. This keeps diffs clean, reviews easy, and risk contained.

---

*Part of the agent-spec Simplicity First standard. See `coding-standards/SIMPLICITY-FIRST.md`.*
