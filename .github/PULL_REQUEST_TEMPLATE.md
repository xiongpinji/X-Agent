# Pull Request Template

## Description
<!-- Provide a clear and concise description of your changes -->

## Type of Change
<!-- Mark the relevant option with an 'x' -->

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Code refactoring
- [ ] Performance improvement
- [ ] Test coverage improvement

## Related Issues
<!-- Link to related issues using #issue_number -->

Fixes #
Relates to #

## Changes Made
<!-- List the main changes in bullet points -->

- 
- 
- 

## Testing
<!-- Describe the tests you ran and how to reproduce them -->

### Test Coverage
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing performed
- [ ] All tests pass locally

### Test Instructions
```bash
# Commands to run tests
pytest tests/test_your_feature.py
```

## Screenshots (if applicable)
<!-- Add screenshots to help explain your changes -->

## Checklist
<!-- Mark completed items with an 'x' -->

### Code Quality
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings
- [ ] I have run `ruff check .` and fixed all issues
- [ ] I have run `mypy backend/` and fixed all type errors

### Documentation
- [ ] I have updated the documentation accordingly
- [ ] I have added/updated docstrings for new/modified functions
- [ ] I have updated the README if needed
- [ ] I have updated the CHANGELOG if needed

### Testing
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Test coverage has not decreased

### Security
- [ ] I have checked for security vulnerabilities
- [ ] I have not introduced any hardcoded secrets or credentials
- [ ] I have validated all user inputs
- [ ] I have used parameterized queries for database operations

### Git
- [ ] My commits follow the conventional commit format
- [ ] I have rebased my branch on the latest develop
- [ ] I have resolved all merge conflicts

## Additional Notes
<!-- Add any additional context or notes for reviewers -->

## Reviewer Checklist
<!-- For reviewers to complete -->

- [ ] Code follows project conventions
- [ ] Tests are adequate and pass
- [ ] Documentation is clear and complete
- [ ] No security concerns
- [ ] Performance impact is acceptable
- [ ] Breaking changes are documented
