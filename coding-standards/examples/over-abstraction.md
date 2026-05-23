# Over-Abstraction Anti-Pattern

> **The most common LLM coding failure: building an enterprise architecture for a problem that needs a function.**

When asked to implement something simple, LLMs tend to reach for design patterns they've seen in training data — Strategy, Factory, Builder, Abstract Base Classes — even when a simple function would suffice.

---

## Example 1: Strategy Pattern for a Simple Calculation

**User request:** *"Add a function to calculate discount"*

### ❌ What LLMs Do (Over-Engineered)

**Python:**
```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Protocol

class DiscountStrategy(ABC):
    @abstractmethod
    def calculate(self, amount: float) -> float:
        pass

class PercentageDiscount(DiscountStrategy):
    def __init__(self, percentage: float):
        self.percentage = percentage
    
    def calculate(self, amount: float) -> float:
        return amount * (self.percentage / 100)

class FixedDiscount(DiscountStrategy):
    def __init__(self, fixed_amount: float):
        self.fixed_amount = fixed_amount
    
    def calculate(self, amount: float) -> float:
        return min(self.fixed_amount, amount)

@dataclass
class DiscountConfig:
    strategy: DiscountStrategy
    min_purchase: float = 0.0
    max_discount: float = float('inf')

class DiscountCalculator:
    def __init__(self, config: DiscountConfig):
        self.config = config
    
    def apply_discount(self, amount: float) -> float:
        if amount < self.config.min_purchase:
            return 0
        discount = self.config.strategy.calculate(amount)
        return min(discount, self.config.max_discount)

# Usage requires 5 lines of setup for a simple calculation
```

**Java:**
```java
public interface DiscountStrategy {
    double calculate(double amount);
}

public class PercentageDiscount implements DiscountStrategy {
    private final double percentage;
    
    public PercentageDiscount(double percentage) {
        this.percentage = percentage;
    }
    
    @Override
    public double calculate(double amount) {
        return amount * (percentage / 100);
    }
}

public class FixedDiscount implements DiscountStrategy {
    private final double fixedAmount;
    // ... another 20 lines
}

public class DiscountConfig {
    private final DiscountStrategy strategy;
    private final double minPurchase;
    private final double maxDiscount;
    // ... constructor, getters, builder pattern ...
}

public class DiscountCalculator {
    private final DiscountConfig config;
    // ... another 30 lines
}
```

**Problems:**
- 4 classes, 2 interfaces, 1 dataclass for a one-line calculation
- No evidence that multiple discount types are needed
- Speculative "min_purchase" and "max_discount" — nobody asked for those

### ✅ What Should Happen (Simple)

**Python:**
```python
def calculate_discount(amount: float, percent: float) -> float:
    """Calculate discount amount. percent should be 0-100."""
    return amount * (percent / 100)
```

**Java:**
```java
public static double calculateDiscount(double amount, double percent) {
    return amount * (percent / 100);
}
```

**When to add complexity:** Only when you actually need multiple discount types. If that requirement comes later, refactor then.

---

## Example 2: Service Layer for Simple CRUD

**User request:** *"Save user preferences to database"*

### ❌ What LLMs Do (Over-Engineered)

**Python:**
```python
class PreferenceManager:
    def __init__(self, db, cache=None, validator=None):
        self.db = db
        self.cache = cache or InMemoryCache()
        self.validator = validator or DefaultValidator()
    
    def save(self, user_id: int, prefs: dict, 
             merge: bool = True, 
             validate: bool = True,
             notify: bool = False) -> bool:
        if validate:
            errors = self.validator.validate(prefs)
            if errors:
                raise ValidationError(errors)
        
        existing = self.get(user_id)
        if merge and existing:
            prefs = {**existing, **prefs}
        
        self.db.upsert('preferences', user_id, prefs)
        self.cache.invalidate(f'prefs:{user_id}')
        
        if notify:
            self.notify_preference_change(user_id, prefs)
        
        return True
```

**Problems:**
- Cache nobody asked for
- Validator nobody asked for
- Merge logic nobody asked for
- Notification system nobody asked for

### ✅ What Should Happen (Simple)

**Python:**
```python
def save_preferences(user_id: int, preferences: dict, db) -> None:
    """Save user preferences to database."""
    db.upsert('preferences', user_id, preferences)
```

**Java:**
```java
public void savePreferences(Long userId, Map<String, Object> preferences) {
    preferenceRepository.save(new UserPreference(userId, preferences));
}
```

---

> **Key Takeaway:** If you can solve the problem with a function, don't build a class. If you can solve it with a class, don't build a framework. Complexity should be justified by proven requirements, not anticipated ones.

---

*Part of the agent-spec Simplicity First standard. See `coding-standards/SIMPLICITY-FIRST.md`.*
