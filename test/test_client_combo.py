"""客户端下拉刷新：菜单开着时结果暂存、收起后应用（纯逻辑，无需界面）。

背景：qfluentwidgets.ComboBox 是 QPushButton 套壳，不走原生
showPopup/hidePopup，主窗口改用 _client_popup_open 标记菜单状态。
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fake_window():
    from OAT.app.main_window import MainWindow
    w = MainWindow.__new__(MainWindow)
    w.selected_hwnd = None
    w._client_item_map = {}
    w._pending_client_items = None
    w._client_popup_open = False
    w.applied = []
    w._set_client_items = lambda items: w.applied.append(list(items))
    return w


def test_apply_direct_when_popup_closed():
    w = _fake_window()
    items = [("a", None)]
    w._apply_client_list(items)
    assert w.applied == [items]
    assert w._pending_client_items is None


def test_stash_while_popup_open_then_apply_on_close():
    w = _fake_window()
    w._client_popup_open = True  # 模拟下拉菜单正开着（popup_opened 已触发）
    items = [("b", None)]
    w._apply_client_list(items)
    assert w.applied == []
    assert w._pending_client_items == items
    w._apply_pending_client_list()  # popup_closed
    assert w.applied == [items]
    assert w._pending_client_items is None
    assert w._client_popup_open is False


def test_popup_open_handler_sets_flag_and_refreshes():
    w = _fake_window()
    called = []
    w.refresh_clients_async = lambda: called.append(1)
    w._on_client_popup_opened()
    assert w._client_popup_open is True and called == [1]


def test_empty_items_noop():
    w = _fake_window()
    w._client_popup_open = True
    w._apply_client_list([])
    assert w.applied == [] and w._pending_client_items is None


def test_combo_hooks_show_menu_not_popup():
    """ClientComboBox 必须钩 _showComboMenu（真入口），而不是已死的 showPopup。"""
    import inspect
    from OAT.app.home_page import ClientComboBox
    assert "_showComboMenu" in ClientComboBox.__dict__
    assert "showPopup" not in ClientComboBox.__dict__
    src = inspect.getsource(ClientComboBox._showComboMenu)
    assert "popup_opened" in src and "popup_closed" in src
