# Celery Chain Pattern - Best Practices

**Status:** Guidelines for avoiding common Celery chain errors

## The Problem

When using Celery chains with `.s()`, the result from the previous task is **automatically passed** as the first argument to the next task. This causes `TypeError` if the function signature doesn't expect it.

## Example Error

```
TypeError: task_name() takes 1 positional argument but 2 were given
```

This happens when:
```python
chain(
    task_a.s(),
    task_b.s(arg1),  # ← task_b receives result from task_a AND arg1
    task_c.s()
)
```

## The Solution Pattern

**Always include `previous_result=None` parameter in chained tasks:**

```python
@celery_app.task(bind=True)
def my_chained_task(self, previous_result=None, my_arg=None):
    """Task that can be used in chains"""
    
    # Log the previous result if present
    if previous_result and isinstance(previous_result, dict):
        logger.info(f"Received from previous task: {previous_result.get('message', 'N/A')}")
    
    # Your task logic here
    logger.info(f"Starting my_chained_task with arg: {my_arg}")
    
    # ... do work ...
    
    return {
        'status': 'success',
        'message': 'Task completed',
        'data': result_data
    }
```

## Task Chain in cc-registry-v2

Our main data population workflow uses this pattern:

```python
# In populate_registry_task
workflow = chain(
    store_yaml_data_task.s(),                    # Returns: {'status': 'success', ...}
    clone_repositories_task.s(collection_slugs), # Receives result + collection_slugs
    parse_stored_data_task.s()                   # Receives result from clone
)
```

**All three tasks follow the pattern:**

### 1. store_yaml_data_task
```python
@celery_app.task(bind=True)
def store_yaml_data_task(self, yaml_content: str = None):
    # First in chain, no previous_result needed
    return {'status': 'success', 'collections_count': count}
```

### 2. clone_repositories_task
```python
@celery_app.task(bind=True)
def clone_repositories_task(self, previous_result=None, collection_slugs: List[str] = None):
    # Receives result from store_yaml_data_task
    if previous_result:
        logger.info(f"Previous: {previous_result.get('message')}")
    return {'status': 'success', 'files_stored': count}
```

### 3. parse_stored_data_task
```python
@celery_app.task(bind=True)
def parse_stored_data_task(self, previous_result=None):
    # Receives result from clone_repositories_task
    if previous_result:
        logger.info(f"Previous: {previous_result.get('message')}")
    return {'status': 'success', 'codebundles_created': count}
```

## Key Rules

### ✅ DO:
1. **Always add `previous_result=None`** as first parameter (after `self`) in chained tasks
2. **Log the previous result** for debugging and traceability
3. **Return dict with status** for consistent chain results
4. **Use `.s()` for chaining** (signature primitive)
5. **Use `apply_async()` to start chains** (not `apply()`)

### ❌ DON'T:
1. **Don't omit `previous_result`** parameter in chained tasks
2. **Don't use `.apply()`** - it executes synchronously
3. **Don't guess parameters** - always check what previous task returns
4. **Don't chain without `bind=True`** - you need `self` for task methods

## Testing Chains

To test if a chain is configured correctly:

```python
# Test individual task
result = my_task.apply_async(args=['arg1'])
print(result.get())

# Test chain
workflow = chain(task_a.s(), task_b.s(arg1), task_c.s())
result = workflow.apply_async()
print(result.get())  # Returns result of last task
```

## Common Patterns

### Pattern 1: Pass Data Through Chain
```python
@celery_app.task(bind=True)
def task_a(self):
    return {'user_id': 123, 'data': 'important'}

@celery_app.task(bind=True)
def task_b(self, previous_result=None):
    user_id = previous_result.get('user_id') if previous_result else None
    # Use user_id...
    return {'status': 'success'}
```

### Pattern 2: Ignore Previous Result
```python
@celery_app.task(bind=True)
def task_c(self, previous_result=None, my_specific_arg=None):
    # Don't need previous result, just accept it
    # Use my_specific_arg...
    return {'status': 'success'}
```

### Pattern 3: Conditional Chain
```python
@celery_app.task(bind=True)
def task_d(self, previous_result=None):
    if previous_result and previous_result.get('status') == 'success':
        # Continue processing
        pass
    else:
        # Handle failure from previous task
        raise ValueError("Previous task failed")
```

## Debugging Chain Issues

### Check Task Signature
```python
# In task definition
@celery_app.task(bind=True)
def my_task(self, previous_result=None, arg1=None, arg2=None):
    logger.info(f"Task started with: previous_result={previous_result}, arg1={arg1}, arg2={arg2}")
```

### Check Chain Definition
```python
# When creating chain
logger.info("Creating chain...")
workflow = chain(
    task_a.s(),
    task_b.s('explicit_arg'),  # This arg comes AFTER previous_result
    task_c.s()
)
logger.info(f"Chain created: {workflow}")
```

### Check Task Logs
```bash
# View worker logs
docker-compose logs worker | grep "task_name"

# Check database for task errors
docker exec registry-database psql -U user -d codecollection_registry \
  -c "SELECT task_name, status, error_message FROM task_executions WHERE status = 'FAILURE' ORDER BY created_at DESC LIMIT 10;"
```

## Related Files

- `backend/app/tasks/data_tasks.py` - Main data workflow tasks
- `backend/app/tasks/workflow_tasks.py` - Sync/parse/enhance workflows
- `docs/WORKFLOW_FIX.md` - Workflow `.apply()` vs `.apply_async()` fix

## References

- [Celery Canvas Documentation](https://docs.celeryproject.org/en/stable/userguide/canvas.html)
- [Celery Chains](https://docs.celeryproject.org/en/stable/userguide/canvas.html#chains)
- [Celery Signatures](https://docs.celeryproject.org/en/stable/userguide/canvas.html#signatures)

---

**Last Updated:** 2026-01-24  
**Related Issues:** Fixed `store_yaml_data_task`, `clone_repositories_task`, `parse_stored_data_task` chain errors
