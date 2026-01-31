# DokyDoc Testing Strategy

## 🎯 Testing Philosophy

**"Test Early, Test Often, Automate Wisely"**

We use a layered approach combining manual and automated testing to ensure quality while maintaining development velocity.

---

## 📊 Testing Layers

```
┌─────────────────────────────────────────────────────────┐
│  Manual Exploratory Testing                             │
│  • UX/UI issues                                         │
│  • Edge cases                                           │
│  • New feature validation                              │
│  Time: 10-20% of testing effort                        │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  E2E Tests (Playwright)                                 │
│  • Critical user flows (5-10 tests)                    │
│  • Login → Dashboard                                    │
│  • User management flows                               │
│  • Multi-tenant isolation                              │
│  Time: ~5-10 minutes                                    │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  API Integration Tests (pytest)                         │
│  • All endpoints                                        │
│  • Auth & permissions                                   │
│  • Tenant isolation                                     │
│  • Error handling                                       │
│  Time: ~2-5 minutes                                     │
└─────────────────────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────────────────────┐
│  Unit Tests (pytest/Jest)                              │
│  • Business logic                                       │
│  • Utility functions                                    │
│  • Component logic                                      │
│  Time: ~30 seconds                                      │
└─────────────────────────────────────────────────────────┘
```

---

## 🚀 Testing Phases

### Phase 1: Manual Testing (CURRENT - Week 1-2)
**Goal**: Get application working and understand user flows

**Activities**:
- [ ] Test login with different roles (CXO, Developer, PM, BA)
- [ ] Test user invitation flow
- [ ] Test document upload and viewing
- [ ] Test task creation and management
- [ ] Test billing page
- [ ] Test tenant registration
- [ ] Create manual test checklist (see below)

**Tools**: Browser, Postman

**Time Investment**: 4-8 hours initially, 1-2 hours per new feature

---

### Phase 2: API Test Automation (Week 2-3)
**Goal**: Automate backend API testing for fast regression testing

**Setup**:
```bash
cd backend
pytest tests/ -v
```

**Coverage Targets**:
- ✅ Authentication: 100%
- ✅ User Management: 95%
- ✅ Tenant Isolation: 100%
- ✅ Permissions: 95%
- ✅ Documents: 80%
- ✅ Tasks: 80%

**Benefits**:
- Runs in 2-5 minutes
- Catches bugs before frontend
- Validates security (tenant isolation)
- Enables confident refactoring

**Time Investment**: 8-16 hours initial setup, 30 mins per new endpoint

---

### Phase 3: E2E Critical Flows (Week 4)
**Goal**: Automate 5-10 critical user journeys

**Priority Flows**:
1. New tenant registration → Login → Dashboard
2. Invite user → User accepts → Login
3. Upload document → View document → Download
4. Create task → Assign → Complete
5. View billing → Add balance
6. Admin locks out another admin (should prevent)

**Setup**:
```bash
cd frontend
npm install -D @playwright/test
npx playwright install
npx playwright test --ui
```

**Benefits**:
- Tests full stack integration
- Catches UI/UX bugs
- Validates browser compatibility
- Smoke test before deployment

**Time Investment**: 12-20 hours initial setup, 1-2 hours per flow

---

### Phase 4: Component Tests (Optional)
**Goal**: Test complex UI components in isolation

**When to use**:
- Reusable component library
- Complex form validation
- Custom hooks

**Time Investment**: Only if time permits

---

## ✅ Manual Testing Checklist

### Authentication Flow
- [ ] Register new tenant with valid data
- [ ] Register with duplicate subdomain (should fail)
- [ ] Login with correct credentials
- [ ] Login with wrong password (should fail)
- [ ] Logout and verify session cleared
- [ ] Access protected route without login (should redirect)

### User Management (CXO Only)
- [ ] View users list
- [ ] Invite user with Developer role
- [ ] Invite user with multiple roles
- [ ] Invite duplicate email (should fail)
- [ ] Edit user roles
- [ ] Try to deactivate own account (should prevent)
- [ ] Deactivate another user
- [ ] Reactivate user
- [ ] Search users by email

### Multi-Tenancy Isolation
- [ ] Login as Tenant1 admin → View users (should see only Tenant1)
- [ ] Login as Tenant2 admin → View users (should see only Tenant2)
- [ ] Login as Tenant1 → View documents (should see only Tenant1)
- [ ] Try to access Tenant2 data via API (should fail)

### Permissions (RBAC)
- [ ] Login as CXO → Access all features ✅
- [ ] Login as Developer → Cannot access user management ❌
- [ ] Login as PM → Cannot access code components ❌
- [ ] Login as BA → Cannot access billing ❌

### Document Management
- [ ] Upload document (PDF, DOCX)
- [ ] View document details
- [ ] Download document
- [ ] Delete document
- [ ] Upload invalid file type (should fail)

### Task Management
- [ ] Create task with title only
- [ ] Create task with all fields
- [ ] Assign task to user
- [ ] Update task status (todo → in_progress → done)
- [ ] Add comment to task
- [ ] Filter tasks by status
- [ ] Filter tasks by priority

---

## 🔧 Running Tests

### Backend Tests
```bash
# Run all tests
cd backend
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_user_management.py::TestInviteUser -v

# Run and stop on first failure
pytest tests/ -x
```

### Frontend E2E Tests
```bash
# Install dependencies
cd frontend
npm install -D @playwright/test
npx playwright install

# Run tests headless
npx playwright test

# Run with UI (interactive)
npx playwright test --ui

# Run in headed mode (see browser)
npx playwright test --headed

# Run specific test
npx playwright test e2e/user-management.spec.ts
```

---

## 📈 Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Backend API Test Coverage | 80%+ | 0% → Setup in progress |
| E2E Critical Flows Covered | 5-10 | 0 → Examples created |
| Test Execution Time | < 10 min | N/A |
| Manual Test Pass Rate | 100% | In progress |
| Bugs Found Pre-Production | Track | Starting |

---

## 🎓 Learning Resources

- **Pytest**: https://docs.pytest.org/
- **FastAPI Testing**: https://fastapi.tiangolo.com/tutorial/testing/
- **Playwright**: https://playwright.dev/
- **React Testing Library**: https://testing-library.com/react

---

## 📝 Next Steps

1. **This Week**: Complete manual testing checklist
2. **Next Week**: Get backend API tests running (already set up!)
3. **Week After**: Pick 3 critical E2E flows to automate
4. **Ongoing**: Add tests for each new feature

---

## 🤔 When to Use Each Type

| Scenario | Manual | API Test | E2E Test |
|----------|--------|----------|----------|
| New feature exploration | ✅ | ❌ | ❌ |
| UX/Design validation | ✅ | ❌ | ⚠️ |
| Security (tenant isolation) | ⚠️ | ✅ | ✅ |
| Performance testing | ⚠️ | ✅ | ✅ |
| Browser compatibility | ❌ | ❌ | ✅ |
| Regression testing | ❌ | ✅ | ✅ |
| Edge cases | ✅ | ✅ | ❌ |

Legend: ✅ Best choice | ⚠️ Possible | ❌ Not suitable

---

**Remember**: Start with manual testing to understand the system, then automate the repetitive parts. Don't try to automate everything at once!
