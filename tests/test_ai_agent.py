from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from modules.ai_agent import GeminiAgent


def _patch_hw_and_client(mock_client):
    return (
        patch("modules.ai_agent.genai.Client", return_value=mock_client),
        patch("modules.tools.info_cpu_nome", return_value="Test CPU"),
        patch("modules.tools.monitora_gpu", return_value={"gpu": "Test GPU"}),
        patch("modules.tools.info_versioni_sistema", return_value={"windows": "Windows 11 Test", "driver_gpu": "555.00"}),
    )


def test_gemini_agent_init_and_dynamic_prompt():
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_chat.send_message.return_value = SimpleNamespace(text="Risposta OK")
    mock_client.chats.create.return_value = mock_chat

    p1, p2, p3, p4 = _patch_hw_and_client(mock_client)
    with p1, p2, p3, p4:
        ag = GeminiAgent()
        assert ag.errore_init is None
        assert "Test CPU" in ag._config_chat.system_instruction
        assert "Test GPU" in ag._config_chat.system_instruction
        assert ag.invia("ciao") == "Risposta OK"


def test_gemini_agent_fallback_on_503_and_404():
    mock_client = MagicMock()
    chat_fail_503 = MagicMock()
    chat_fail_503.send_message.side_effect = RuntimeError("503 UNAVAILABLE")
    chat_fail_503.get_history.return_value = ["prev"]

    chat_fail_404 = MagicMock()
    chat_fail_404.send_message.side_effect = RuntimeError("404 NOT_FOUND")
    chat_fail_404.get_history.return_value = ["prev"]

    chat_ok = MagicMock()
    chat_ok.send_message.return_value = SimpleNamespace(text="Risposta dal fallback")

    mock_client.chats.create.side_effect = [chat_fail_503, chat_fail_404, chat_ok]
    stati = []

    p1, p2, p3, p4 = _patch_hw_and_client(mock_client)
    with p1, p2, p3, p4:
        ag = GeminiAgent()
        risposta = ag.invia("test fallback", on_retry=stati.append)

    assert risposta == "Risposta dal fallback"
    assert len(stati) == 2
    assert ag.modello_corrente == "gemini-3.5-flash-lite"


def test_gemini_agent_non_retryable_error():
    mock_client = MagicMock()
    mock_chat = MagicMock()
    mock_chat.send_message.side_effect = ValueError("Bad request")
    mock_client.chats.create.return_value = mock_chat

    p1, p2, p3, p4 = _patch_hw_and_client(mock_client)
    with p1, p2, p3, p4:
        ag = GeminiAgent()
        res = ag.invia("ciao")
    assert res.startswith("Errore:")


def test_gemini_agent_offline_init_error():
    with patch("modules.ai_agent.genai.Client", side_effect=RuntimeError("No API Key")):
        ag = GeminiAgent()
        assert ag.errore_init == "No API Key"
        res = ag.invia("ciao")
        assert "non disponibile" in res.lower()


def test_gemini_agent_hitl_confirmation_blocks_and_allows():
    mock_client = MagicMock()
    mock_client.chats.create.return_value = MagicMock()

    p1, p2, p3, p4 = _patch_hw_and_client(mock_client)
    with p1, p2, p3, p4:
        ag_deny = GeminiAgent(confirm_callback=lambda msg: False)
        tools_map = {getattr(fn, "__name__", ""): fn for fn in ag_deny._config_chat.tools}

        with patch("modules.tools.termina_processo") as m_kill, \
             patch("modules.tools.disabilita_app_avvio") as m_dis, \
             patch("modules.tools.attiva_modalita_prestazioni") as m_perf, \
             patch("modules.tools.pulisci_file_temporanei") as m_temp:
            assert "annullata" in tools_map["termina_processo"]("notepad.exe").lower()
            assert "annullata" in tools_map["disabilita_app_avvio"]("SomeApp").lower()
            assert "annullata" in tools_map["attiva_modalita_prestazioni"]().lower()
            assert "annullata" in tools_map["pulisci_file_temporanei"]().lower()
            m_kill.assert_not_called()
            m_dis.assert_not_called()
            m_perf.assert_not_called()
            m_temp.assert_not_called()

        ag_allow = GeminiAgent(confirm_callback=lambda msg: True)
        tools_allow = {getattr(fn, "__name__", ""): fn for fn in ag_allow._config_chat.tools}
        with patch("modules.tools.termina_processo", return_value="OK_KILL") as m_kill2, \
             patch("modules.tools.disabilita_app_avvio", return_value="OK_DIS") as m_dis2, \
             patch("modules.tools.attiva_modalita_prestazioni", return_value="OK_PERF") as m_perf2, \
             patch("modules.tools.pulisci_file_temporanei", return_value="OK_TEMP") as m_temp2:
            assert tools_allow["termina_processo"]("notepad.exe") == "OK_KILL"
            assert tools_allow["disabilita_app_avvio"]("SomeApp") == "OK_DIS"
            assert tools_allow["attiva_modalita_prestazioni"]() == "OK_PERF"
            assert tools_allow["pulisci_file_temporanei"]() == "OK_TEMP"
            m_kill2.assert_called_once_with("notepad.exe")
            m_dis2.assert_called_once_with("SomeApp")
            m_perf2.assert_called_once()
            m_temp2.assert_called_once()
