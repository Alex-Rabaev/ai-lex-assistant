"""Unit tests for analysis router endpoint definitions.

These tests verify that all endpoints are properly defined
and the router can be imported without errors.
"""

import pytest
from app.modules.analysis.router import router


class TestRouterEndpoints:
    """Tests that all required endpoints exist."""
    
    def _get_routes(self):
        """Get all routes as {method: path} pairs."""
        routes = []
        for route in router.routes:
            if hasattr(route, "methods"):
                for method in route.methods:
                    routes.append((method, route.path))
        return routes
    
    def test_get_analysis_config(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/analysis-config") in routes
    
    def test_put_analysis_config(self):
        routes = self._get_routes()
        assert ("PUT", "/assistants/{assistant_id}/analysis-config") in routes
    
    def test_post_generate_config(self):
        routes = self._get_routes()
        assert ("POST", "/assistants/{assistant_id}/analysis-config/generate") in routes
    
    def test_get_suggestions(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/analysis-config/suggestions") in routes
    
    def test_post_create_snapshot(self):
        routes = self._get_routes()
        assert ("POST", "/assistants/{assistant_id}/analysis/snapshot") in routes
    
    def test_get_list_snapshots(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/analysis/snapshots") in routes
    
    def test_get_snapshot_by_id(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/analysis/snapshots/{execution_id}") in routes
    
    def test_patch_snapshot(self):
        routes = self._get_routes()
        assert ("PATCH", "/analysis/snapshots/{execution_id}") in routes
    
    def test_get_conversation_analytic_meta(self):
        routes = self._get_routes()
        assert ("GET", "/conversations/{conversation_id}/analytic-meta") in routes
    
    def test_get_assistant_analytic_meta(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/analytic-meta") in routes
    
    def test_post_mock_respondents(self):
        routes = self._get_routes()
        assert ("POST", "/assistants/{assistant_id}/mock-respondents") in routes
    
    def test_delete_snapshot(self):
        routes = self._get_routes()
        assert ("DELETE", "/analysis/snapshots/{execution_id}") in routes

    def test_export_single_messages(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/interlocutors/{interlocutor_id}/export/messages") in routes

    def test_export_bulk_messages(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/export/messages") in routes

    def test_export_bulk_respondents(self):
        routes = self._get_routes()
        assert ("GET", "/assistants/{assistant_id}/export/respondents") in routes

    def test_delete_mock_respondents(self):
        routes = self._get_routes()
        assert ("DELETE", "/assistants/{assistant_id}/mock-respondents") in routes

    def test_total_endpoint_count(self):
        """Verify expected number of endpoints."""
        routes = self._get_routes()
        assert len(routes) == 16


class TestRouterRegistration:
    """Tests that router is registered in main app."""
    
    def test_router_in_main(self):
        """Verify analysis router is included in main app."""
        from app.main import app
        
        paths = [route.path for route in app.routes]
        assert any("/analysis-config" in p for p in paths)
        assert any("/analysis/snapshot" in p for p in paths)
        assert any("/analytic-meta" in p for p in paths)
        assert any("/export/messages" in p for p in paths)
        assert any("/export/respondents" in p for p in paths)
