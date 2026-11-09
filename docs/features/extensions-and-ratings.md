# Feature: Loan extensions and ratings

*Owner: Keitha*

## Loan extensions

Sometimes a borrower needs an item a little longer. Instead of just keeping it (and becoming overdue), they ask the owner for more time.

1. The borrower chooses **Ask for more time on a loan**, gives the loan id, how many extra hours (1 to 24) and an optional reason.
2. The owner is notified and chooses **Extension requests for my items** to approve or decline.
3. If approved, the loan's return time moves later. If the loan was already **Overdue** and the new time is in the future, it goes back to **Handed over**, so the borrower can borrow again.

Rules:

- Only the borrower can ask, and only while they have the item (Handed over or Overdue).
- One pending request per loan at a time.
- An extension can never run into someone else's confirmed booking of the same item. This is checked when asking **and** again when approving.
- Only the owner can approve or decline, and each request can be answered once.

## Ratings

After an item is returned, the borrower and the owner can each rate the other **once**, from 1 to 5 stars, with an optional comment. **Ratings for a user** shows someone's average and all their ratings, which helps lenders decide whom to trust.

## OOP design

| Class | Concept |
|---|---|
| `ExtensionRequest` | Encapsulation: status changes only through `approve()` / `decline()`, and each can happen once |
| `Rating` | Validation in the constructor (1-5 stars, no self-rating) and read-only properties |
| `Loan.extend_to()` | Extends the existing state machine with a guarded method instead of exposing `_due_at` |
| `ExtensionManager`, `RatingBook` | Services that depend on `Community` (composition) |
| `ExtensionsAndRatingsPlugin` | Inheritance from `MenuPlugin`, and polymorphism: different menu for students and admins |

## Files

```
borrowmate/models/loan.py                # + extend_to(), OVERDUE -> HANDED_OVER transition
borrowmate/models/feedback.py            # ExtensionRequest, ExtensionStatus, Rating
borrowmate/services/feedback_service.py  # ExtensionManager, RatingBook
borrowmate/plugins/extensions_ratings.py # menu options (loaded automatically)
tests/test_extensions_ratings.py         # 7 tests
```
