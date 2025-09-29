# Tag System Concept

This document explains the concept of the **header with the filter system** and the **permission system** for implementation in Windsurf programming, including example UI wireframes.

---

## 1. Header & Filter System

The header serves as the central navigation and control area. It contains:

### 1.1 Filter Components
- **Search bar**: free text search across posts, replies, and tags.
- **Tag filter**: dropdown or multi-select to show only posts with selected tags.
- **Sort options**: newest, most voted, most replies.
- **User filter** (admin/mod only): filter posts/replies from specific users.

### 1.2 Tag Management
- Tags are user‑generated but moderated.
- Admin can **create, rename, delete, or ban** tags.
- Tags appear in the header filter menu dynamically.
- Tags have counters (how many posts/replies use them).

**Example Scenario**: If a user creates a tag like 'offtopic', an admin can ban it if it's frequently abused, preventing new uses while preserving existing references. This helps maintain community standards without data loss.

---

## 2. Permission System

Different user roles have different permissions. The system is hierarchical:

### 2.1 Roles
1. **Guest**
   - Can only see the welcome & login page.
2. **User**
   - Can create posts (limited by daily quota).
   - Can reply to posts (limited by daily quota).
   - Can vote up/down posts and replies.
   - Can use filters and tag search.
3. **Moderator**
   - Can silence users (temporary).
   - Can delete posts/replies.
   - Voting counts **double**.
   - Can manage tags partially (ban tag from being used).
4. **Admin**
   - Full access.
   - Can promote/demote users (to moderator/admin).
   - Can set rate limits and quotas.
   - Can create/delete/ban/rename tags.
   - Access to **stats page** (user ranking, counters, tags).

---

## 3. Interaction Between Header & Permissions

- **Tag filter**: available to all logged-in users.
- **Admin/moderator filters**: additional controls visible only if user role ≥ moderator.
- **Tag creation**: any user can suggest, but only moderators/admins can approve or ban.
- **Auto-silence**: users are automatically silenced if their posts/replies fall below threshold due to voting. Admin/moderator votes weigh more.

---

## 4. Technical Notes for Windsurf

- Use **role-based middleware** for permission checks.
- Store tags in a `tags` table with fields:
  ```sql
  id SERIAL PRIMARY KEY,
  name TEXT UNIQUE,
  status ENUM('active', 'banned'),
  usage_count INT
  ```
- Store user roles in `users.role` column with ENUM: `guest, user, moderator, admin`.
- Header filter pulls live from `tags` table and respects `status`.
- Permissions enforced both in **backend API** and **frontend UI**.

---

## 5. Example UI Wireframes

### 5.1 Guest View
```
+-----------------------------------------------------+
|  Logo   |  Login  |                                 |
+-----------------------------------------------------+
```

### 5.2 User View
```
+----------------------------------------------------------------------------------+
|  Logo  | [Search 🔍] | [Tag ▼] | [Sort ▼] | Profile ⚙️                           |
+----------------------------------------------------------------------------------+
```

### 5.3 Moderator View
```
+------------------------------------------------------------------------------------------------------+
|  Logo  | [Search 🔍] | [Tag ▼] | [Sort ▼] | [User Filter 👤] | Moderator Panel ⚡ | Profile ⚙️       |
+------------------------------------------------------------------------------------------------------+
```

### 5.4 Admin View
```
+---------------------------------------------------------------------------------------------------------------------------+
|  Logo  | [Search 🔍] | [Tag ▼] | [Sort ▼] | [User Filter 👤] | Tag Manager 🏷️ | Stats 📊 | Admin Panel 🛠️ | Profile ⚙️ |
+---------------------------------------------------------------------------------------------------------------------------+
```

---

These wireframes illustrate how the header adapts dynamically depending on user role while maintaining a consistent navigation experience.
