# Feature: "I Need This" requests

*Owner: Stacey*

Searching only finds items someone has already listed. Most students never list their things, so BorrowMate also works the other way round: **you post what you need, and people nearby offer it.**

## How it works

1. A student chooses **Post an 'I Need This' request**: what they need, its category, for how many hours, and how far to ask (default 1 km).
2. Every student within that distance (hostel to hostel) is notified.
3. Nearby students see it under **Requests near me I can help with** and send an offer, even if they never listed the item.
4. The requester opens **My requests and their offers**, sees each offerer's hostel and reliability score, and picks one.
5. BorrowMate lists the item for the chosen lender and creates a **confirmed loan**, ready for the normal handover and return. The other offers are declined politely.
6. Requests that get no accepted offer **expire** (after 24 hours by default) and the requester is told to try a wider radius.

## Rules

- Only students can post or offer (not admins or suspended accounts).
- You cannot offer on your own request, or offer twice on the same one.
- You can only offer if you are inside the request's radius.
- Only the person who posted can choose an offer or cancel the request.
- All normal borrowing rules still apply when an offer is accepted (trust level, overdue loans, loan limit). They are checked **before** anything is created, so a refusal leaves no half-made item or loan behind.

## OOP design

| Class | Concept |
|---|---|
| `NeedRequest` | Encapsulation and composition: it owns its `Offer` objects and only hands out copies of the list |
| `Offer` | Status can only change once, through the request that owns it |
| `NeedStatus`, `OfferStatus` | Enums instead of strings |
| `NeedBoard` | A service that reuses `Inventory`, `ItemFactory` and `LoanManager` instead of duplicating their rules |
| `NeedRequestsPlugin` | Inheritance from `MenuPlugin`, polymorphic menus, and the `on_tick()` hook to expire old requests |

## Files

```
borrowmate/models/need.py            # NeedRequest, Offer, NeedStatus, OfferStatus
borrowmate/services/need_board.py    # NeedBoard
borrowmate/plugins/need_requests.py  # menu options (loaded automatically)
tests/test_need_requests.py          # 6 tests
```
