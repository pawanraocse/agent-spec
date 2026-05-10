# Angular Standards

> **These rules apply whenever the agent detects an Angular project.**

## 1. Architecture & Components
- **Smart vs. Dumb**: Strictly separate Smart Components (Routable, injects services, manages state) from Dumb/Presentation Components (Only uses `@Input()` and `@Output()`, pure UI).
- **Standalone Components**: Default to Standalone components (`standalone: true`). Avoid creating new `NgModule`s unless maintaining legacy code.
- **OnPush Strategy**: Set `changeDetection: ChangeDetectionStrategy.OnPush` by default on all presentation components to maximize performance.

## 2. State & RxJS
- **Async Pipe**: Heavily favor using the `| async` pipe in HTML templates over manually subscribing in the TypeScript file.
- **Declarative RxJS**: Combine streams using `combineLatest`, `switchMap`, and `withLatestFrom` rather than nesting `subscribe()` calls (the subscribe pyramid of doom).
- **Cleanup**: If you *must* manually subscribe, you MUST clean it up in `ngOnDestroy` (using `takeUntilDestroyed` or a Subject).

## 3. Services
- **Provided In Root**: Default to `@Injectable({ providedIn: 'root' })` for singletons.
- **Stateless by Default**: Services handling HTTP calls must be stateless. State should be managed in dedicated State Services (using `BehaviorSubject` or Signals).

## 4. New Angular Features (v16+)
- **Signals**: Use Signals for synchronous reactive state management. Prefer Signals over `BehaviorSubject` for local component state.
- **Control Flow**: Use the new built-in control flow (`@if`, `@for`) instead of the legacy structural directives (`*ngIf`, `*ngFor`).
- **Required Inputs**: Use `@Input({ required: true })` for mandatory component inputs.

## 5. Typing & Linting
- **Strict Mode**: `strict: true` must be enabled in `tsconfig.json`. No `any` types allowed unless interacting with untyped third-party legacy JS.
- **Interfaces over Classes**: Use `interface` for data models and API payloads. Only use `class` if the object requires methods.
