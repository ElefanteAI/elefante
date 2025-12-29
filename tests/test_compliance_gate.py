#!/usr/bin/env python3
"""
Test script for v1.6.0 Compliance Gate
"""

from src.mcp.server import ElefanteMCPServer
import asyncio

async def test_gate():
    server = ElefanteMCPServer()
    
    # Test 1: Gate should BLOCK add without search
    print('=== Test 1: Add without search ===')
    result = server._check_compliance_gate('elefanteMemoryAdd')
    print(f'Gate result: {result}')
    assert result is not None, 'Should be blocked'
    assert result['gate_status'] == 'BLOCKED'
    print('✅ BLOCKED as expected')
    
    # Test 2: Search should pass (not gated)
    print('\n=== Test 2: Search (not gated) ===')
    result = server._check_compliance_gate('elefanteMemorySearch')
    print(f'Gate result: {result}')
    assert result is None, 'Should pass'
    print('✅ PASSED as expected')
    
    # Test 3: All gated tools should be blocked
    print('\n=== Test 3: All gated tools blocked ===')
    gated_tools = [
        'elefanteMemoryAdd',
        'elefanteGraphEntityCreate',
        'elefanteGraphRelationshipCreate',
        'elefanteGraphConnect'
    ]
    for tool in gated_tools:
        result = server._check_compliance_gate(tool)
        assert result is not None and result['gate_status'] == 'BLOCKED', f'{tool} should be blocked'
        print(f'  ✅ {tool}: BLOCKED')
    
    # Test 4: Simulate search performed
    print('\n=== Test 4: After search performed ===')
    server._compliance_state['search_performed'] = True
    server._compliance_state['search_count'] = 5
    result = server._check_compliance_gate('elefanteMemoryAdd')
    print(f'Gate result: {result}')
    assert result is None, 'Should pass after search'
    print('✅ PASSED - gate unlocked')
    
    # Test 5: All gated tools should now pass
    print('\n=== Test 5: All gated tools pass after search ===')
    for tool in gated_tools:
        result = server._check_compliance_gate(tool)
        assert result is None, f'{tool} should pass after search'
        print(f'  ✅ {tool}: PASS')
    
    # Test 6: Reset gate
    print('\n=== Test 6: Reset gate ===')
    server._reset_compliance_gate()
    assert server._compliance_state['search_performed'] == False
    result = server._check_compliance_gate('elefanteMemoryAdd')
    assert result is not None and result['gate_status'] == 'BLOCKED'
    print('✅ BLOCKED again after reset')
    
    print('\n🎉 All Compliance Gate tests passed!')

if __name__ == '__main__':
    asyncio.run(test_gate())
