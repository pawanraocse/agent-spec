# SOLID Principles

> **The `@ARCHITECT` persona strictly enforces these rules during Gate 3.**

## 1. Single Responsibility Principle (SRP)
A class should have one, and only one, reason to change.
- **Violation**: A `UserService` that validates passwords, sends emails, and generates PDF reports.
- **Enforcement**: Split into `UserValidator`, `UserEmailService`, and `UserReportGenerator`. A file exceeding 400 lines is almost always an SRP violation.

## 2. Open/Closed Principle (OCP)
Software entities should be open for extension, but closed for modification.
- **Violation**: A `PaymentProcessor` with a giant `switch(paymentType)` statement that must be modified every time a new payment method is added.
- **Enforcement**: Use an Interface (`PaymentStrategy`) and inject the implementations.

## 3. Liskov Substitution Principle (LSP)
Subtypes must be substitutable for their base types without altering the correctness of the program.
- **Violation**: A `ReadOnlyFile` subclass that overrides `write()` to throw an `UnsupportedOperationException`.
- **Enforcement**: Interfaces must be segregated so subclasses aren't forced to implement methods they can't fulfill.

## 4. Interface Segregation Principle (ISP)
No client should be forced to depend on methods it does not use.
- **Violation**: A massive `IMachine` interface with `print()`, `staple()`, and `fax()` methods, forcing a simple printer to implement `fax()`.
- **Enforcement**: Create lean, focused interfaces: `IPrinter`, `IStapler`, `IFax`.

## 5. Dependency Inversion Principle (DIP)
High-level modules should not depend on low-level modules. Both should depend on abstractions.
- **Violation**: A `LoginController` that directly instantiates `new MySQLUserRepository()`.
- **Enforcement**: The Controller depends on a `UserRepository` interface. The implementation is injected at runtime (e.g., via Spring DI or Angular constructors).
