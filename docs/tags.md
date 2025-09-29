# Tags & Permissions

## Overview
- **Source**: API behavior defined in `src/backend/app/api/tags.py` with helpers in `src/backend/app/core/tag_access.py`.
- **Purpose**: Control which tags appear to different users based on ban/restriction flags, direct assignments, and role-based visibility.

## Tag States
- **Normal**: `is_banned = false`, `is_restricted = false`. Visible to everyone.
- **Restricted**: `is_restricted = true`. Hidden from non-authorized users unless they are explicitly assigned or granted via roles.
- **Banned**: `is_banned = true`. Hidden from all tag listings and blocked from new usage; only admins can view/manage.

## Visibility Rules
- **Guests / Unauthenticated**: Only see tags where `is_restricted = false`.
- **Authenticated users**: Same as guests plus restricted tags assigned directly to them or shared through their roles.
- **Admins** (`require_admin`): Bypass visibility filters and can view all tags regardless of restriction/ban state.
- **Role-based access**: If a role has access to a restricted tag (`app.tag_visibility.role_id`), every account holding that role inherits tag visibility.

## Key Endpoints
- `GET /tags`: Lists tags respecting visibility rules. Uses `build_access_clause()` to filter restricted tags.
- `GET /tags/list-top`: Returns top tags with usage counts and applies the same visibility filtering for non-admins.
- `POST /tags`: Admin-only. Creates a new tag with `is_restricted = true` by default so admins must explicitly grant visibility.
- `POST /tags/{id}/ban` & `POST /tags/{id}/unban`: Admin-only toggles for ban state.
- `GET /tags/visibility`: Admin-only snapshot of which roles/users can see each restricted tag.
- `GET /tags/visibility/users/{handle}`: Admin-only lookup of tags assigned to a specific user.
- `POST /tags/{id}/visibility/users`: Admin-only assignment of a restricted tag to a user (`app.tag_visibility.account_id`).
- `DELETE /tags/{id}/visibility/users/{handle}`: Admin-only removal of a user assignment.

## Database Structures
- **`app.tags`**: Stores tag metadata and flags (`is_banned`, `is_restricted`).
- **`app.tag_visibility`**: Junction table linking tags to either `account_id` (user-specific access) or `role_id` (role-wide access).
- **`app.account_roles`**: Used to determine inherited visibility when a tag is granted to a role.

## Caching Notes
- Admin responses for `GET /tags` and `GET /tags/list-top` may be cached in Redis for 120 seconds. Cache invalidated on tag create/ban/unban.

## Usage Guidelines
- **Creating tags**: After `POST /tags`, grant visibility to roles/users before the tag is usable by non-admins.
- **Assigning roles**: Prefer role assignments when multiple users need the same restricted tag access.
- **Auditing access**: Use `GET /tags/visibility` (global) and `GET /tags/visibility/users/{handle}` (per-user) to verify assignments.
- **Managing bans**: Banned tags remain in the database for history but should not appear publicly until unbanned.
