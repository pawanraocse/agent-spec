# Java & Spring Boot Standards

> **These rules apply whenever the agent detects a Java/Spring project.**

## 1. Architecture & Layering
- **Strict Layering**: `Controller` -> `Service` -> `Repository`.
- **Controllers are Dumb**: Controllers MUST NOT contain business logic. They only handle HTTP mapping, DTO conversion, and calling the service layer.
- **Entities vs DTOs**: Database `@Entity` classes must NEVER be returned directly from a REST controller. Always map them to a Data Transfer Object (DTO) or Record to prevent over-posting vulnerabilities and lazy-loading exceptions.

## 2. Spring Boot Best Practices
- **Constructor Injection**: Never use `@Autowired` on fields. Always use constructor injection (or Lombok's `@RequiredArgsConstructor`) to ensure dependencies are immutable and testable.
- **Configuration Properties**: Use `@ConfigurationProperties` over `@Value` for structured, type-safe configuration.
- **Global Exception Handling**: Use `@RestControllerAdvice` to map exceptions to standard HTTP status codes rather than handling them in individual controllers.

## 3. Language Features
- **Records**: Use Java 16+ `record` types for all DTOs and immutable data carriers.
- **Optional**: Use `Optional<T>` as a return type for methods that might not find a value (e.g., in Repositories). NEVER use `Optional` as a method argument or a class field.
- **Var**: Use `var` for local variables when the type is obvious from the right-hand side (e.g., `var users = new ArrayList<User>();`).

## 4. Testing
- **Unit Tests**: Use JUnit 5 and Mockito. Test the `Service` layer extensively.
- **Integration Tests**: Use `@SpringBootTest` and Testcontainers to verify repository queries against a real database (PostgreSQL/MySQL), not an H2 memory DB.
- **Naming**: Use descriptive test names: `givenInvalidEmail_whenRegistering_thenThrowsException()`.

## 5. Security
- **Spring Security**: Keep security configuration centralized. Never bypass security config with custom filter hacks.
- **BCrypt**: Always hash passwords using `BCryptPasswordEncoder`.
- **CSRF**: Ensure CSRF protection is enabled for session-based apps, and disabled only for stateless JWT APIs.
