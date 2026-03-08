# Aeromux Database Builder
# Copyright (C) 2025-2026 Nandor Toth <dev@nandortoth.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

from unittest.mock import MagicMock, patch

import httpx
import pytest

from aeromux_db.downloader import _with_retry, download, fetch_text


class TestWithRetry:
    """Tests for the _with_retry helper."""

    @patch("aeromux_db.downloader.time.sleep")
    def test_succeeds_first_attempt(self, mock_sleep: MagicMock) -> None:
        fn = MagicMock(return_value="ok")
        result = _with_retry(fn, "test")
        assert result == "ok"
        fn.assert_called_once()
        mock_sleep.assert_not_called()

    @patch("aeromux_db.downloader.time.sleep")
    def test_retries_on_timeout(self, mock_sleep: MagicMock) -> None:
        fn = MagicMock(side_effect=[httpx.ConnectTimeout("timed out"), "ok"])
        result = _with_retry(fn, "test")
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once_with(5)

    @patch("aeromux_db.downloader.time.sleep")
    def test_retries_on_connect_error(self, mock_sleep: MagicMock) -> None:
        fn = MagicMock(side_effect=[httpx.ConnectError("refused"), "ok"])
        result = _with_retry(fn, "test")
        assert result == "ok"
        assert fn.call_count == 2
        mock_sleep.assert_called_once_with(5)

    @patch("aeromux_db.downloader.time.sleep")
    def test_backoff_doubles(self, mock_sleep: MagicMock) -> None:
        fn = MagicMock(
            side_effect=[
                httpx.ConnectTimeout("t"),
                httpx.ConnectTimeout("t"),
                httpx.ConnectTimeout("t"),
                "ok",
            ]
        )
        result = _with_retry(fn, "test")
        assert result == "ok"
        assert fn.call_count == 4
        assert mock_sleep.call_args_list == [
            ((5,),),
            ((10,),),
            ((20,),),
        ]

    @patch("aeromux_db.downloader.time.sleep")
    def test_fails_after_max_retries(self, mock_sleep: MagicMock) -> None:
        fn = MagicMock(side_effect=httpx.ConnectTimeout("timed out"))
        with pytest.raises(httpx.ConnectTimeout):
            _with_retry(fn, "test")
        assert fn.call_count == 5
        assert mock_sleep.call_count == 4

    @patch("aeromux_db.downloader.time.sleep")
    def test_no_retry_on_http_status_error(self, mock_sleep: MagicMock) -> None:
        request = httpx.Request("GET", "https://example.com")
        response = httpx.Response(404, request=request)
        fn = MagicMock(side_effect=httpx.HTTPStatusError("Not Found", request=request, response=response))
        with pytest.raises(httpx.HTTPStatusError):
            _with_retry(fn, "test")
        fn.assert_called_once()
        mock_sleep.assert_not_called()


class TestDownload:
    """Tests for the download function with retry."""

    @patch("aeromux_db.downloader.time.sleep")
    @patch("aeromux_db.downloader.httpx.stream")
    def test_download_retries_on_timeout(self, mock_stream: MagicMock, mock_sleep: MagicMock, tmp_path) -> None:
        mock_response = MagicMock()
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)
        mock_response.headers = {"content-length": "5"}
        mock_response.iter_bytes.return_value = [b"hello"]

        mock_stream.side_effect = [httpx.ConnectTimeout("timed out"), mock_response]

        result = download("https://example.com/file.zip", "file.zip", tmp_path)
        assert result.size_bytes == 5
        assert result.path == tmp_path / "file.zip"
        assert mock_stream.call_count == 2
        mock_sleep.assert_called_once_with(5)


class TestFetchText:
    """Tests for the fetch_text function with retry."""

    @patch("aeromux_db.downloader.time.sleep")
    @patch("aeromux_db.downloader.httpx.get")
    def test_fetch_text_retries_on_connect_error(self, mock_get: MagicMock, mock_sleep: MagicMock) -> None:
        mock_response = MagicMock()
        mock_response.text = "<xml>data</xml>"
        mock_get.side_effect = [httpx.ConnectError("refused"), mock_response]

        result = fetch_text("https://example.com/listing.xml")
        assert result == "<xml>data</xml>"
        assert mock_get.call_count == 2
        mock_sleep.assert_called_once_with(5)
