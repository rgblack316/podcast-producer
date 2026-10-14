# Auth Testing Playbook (username/password JWT, httpOnly cookies)

1. Mongo: `db.users.find({role:"admin"})` — password_hash starts with `$2b$`; unique index on users.username; index on login_attempts.identifier.
2. API:
```
curl -c cookies.txt -X POST $URL/api/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"BibleBytes!2026"}'
curl -b cookies.txt $URL/api/auth/me
```
Login returns the user (no password_hash) and sets access_token + refresh_token cookies. /me returns the same user.
3. Brute force: 5 wrong passwords for the same ip+username -> 429 for 15 minutes.
4. Inactive users cannot log in. No public registration endpoint exists.
