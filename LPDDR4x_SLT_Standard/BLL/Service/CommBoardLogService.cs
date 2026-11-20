using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using Hsg.Common;

namespace Hsg.BLL.Service
{
    public class CommBoardLogService
    {
        public delegate void DutLogHandler(int t, int g, int d, string txt);
        public delegate void BoardOnlineHandler(int t, int g, bool online);

        private const int TcpPort = 64302;
        private const int UdpPort = 63001;
        private const int MaxBufferedLineLength = 2048;
        private const int TcpErrorLogIntervalMs = 60000;

        private readonly Dictionary<string, Client> _map = new Dictionary<string, Client>();
        private readonly Dictionary<string, StringBuilder> _udpLineBuffers = new Dictionary<string, StringBuilder>();
        private readonly object _udpLock = new object();
        private readonly object _lineBufferLock = new object();
        private readonly CancellationTokenSource _udpCts = new CancellationTokenSource();
        private Task _udpTask;
        private UdpClient _udpClient;
        private bool _udpStarted;
        private BoardOnlineHandler _boardOnlineHandler;
        private readonly object _udpLogFileLock = new object();
        private readonly string _udpLogFilePath = Path.Combine(AppDomain.CurrentDomain.BaseDirectory, "Log", "CommBoardUdp63001.log");

        private class Client
        {
            public int T;
            public int G;
            public TcpClient Tcp;
            public CancellationTokenSource C;
            public DateTime LastTcpErrorLogUtc = DateTime.MinValue;
            public int SuppressedTcpErrorLogs;
        }

        public void Register(string ip, int t, int g, DutLogHandler h)
        {
            if (!_map.ContainsKey(ip))
            {
                var c = new Client { T = t, G = g, C = new CancellationTokenSource() };
                _map[ip] = c;
                Task.Run(() => LoopTcp(ip, c, h, c.C.Token));
            }

            StartUdpIfNeeded(h);
        }

        public void SetBoardOnlineHandler(BoardOnlineHandler handler)
        {
            _boardOnlineHandler = handler;
        }

        public void Stop()
        {
            foreach (var v in _map.Values)
            {
                v.C.Cancel();
                try { v.Tcp?.Close(); } catch { }
            }
            _map.Clear();
            lock (_lineBufferLock)
            {
                _udpLineBuffers.Clear();
            }

            try { _udpCts.Cancel(); } catch { }
            try { _udpClient?.Close(); } catch { }
            _udpClient = null;
            _udpStarted = false;
        }

        private void StartUdpIfNeeded(DutLogHandler h)
        {
            lock (_udpLock)
            {
                if (_udpStarted)
                {
                    return;
                }

                _udpStarted = true;
                _udpTask = Task.Run(() => LoopUdp(h, _udpCts.Token));
            }
        }

        private async Task LoopTcp(string ip, Client c, DutLogHandler h, CancellationToken ct)
        {
            var buf = new List<byte>();
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var t = new TcpClient();
                    await t.ConnectAsync(ip, TcpPort);
                    c.Tcp = t;
                    _boardOnlineHandler?.Invoke(c.T, c.G, true);
                    var s = t.GetStream();
                    var b = new byte[1024];
                    while (!ct.IsCancellationRequested)
                    {
                        int n = await s.ReadAsync(b, 0, 1024, ct);
                        if (n == 0) break;
                        for (int i = 0; i < n; i++) buf.Add(b[i]);
                        while (true)
                        {
                            int nl = buf.IndexOf((byte)'\n');
                            if (nl < 0) break;
                            int e = nl > 0 && buf[nl - 1] == '\r' ? nl - 1 : nl;
                            var lb = buf.GetRange(0, e);
                            buf.RemoveRange(0, nl + 1);
                            string L;
                            try { L = Encoding.UTF8.GetString(lb.ToArray()); }
                            catch { continue; }
                            if (string.IsNullOrWhiteSpace(L)) continue;
                            int d = -1;
                            string tx = L;
                            if (L.StartsWith("[DUT") && L.IndexOf(']') is int eb && eb > 4 && int.TryParse(L.Substring(4, eb - 4), out int id))
                            {
                                d = id;
                                tx = L.Substring(eb + 1).TrimStart();
                            }
                            if (d >= 0) h(c.T, c.G, d, tx);
                        }
                    }
                }
                catch (OperationCanceledException) { break; }
                catch (Exception ex)
                {
                    LogTcpErrorRateLimited(ip, c, ex.Message);
                }
                finally
                {
                    try { c.Tcp?.Close(); } catch { }
                    c.Tcp = null;
                }

                if (!ct.IsCancellationRequested)
                {
                    await Task.Delay(5000, ct);
                }
            }
        }

        private void LogTcpErrorRateLimited(string ip, Client c, string message)
        {
            DateTime now = DateTime.UtcNow;
            if (c.LastTcpErrorLogUtc == DateTime.MinValue ||
                (now - c.LastTcpErrorLogUtc).TotalMilliseconds >= TcpErrorLogIntervalMs)
            {
                string suffix = c.SuppressedTcpErrorLogs > 0 ? $", suppressed:{c.SuppressedTcpErrorLogs}" : "";
                Hlog.D($"CommLogTCP {ip}: {message}{suffix}");
                c.LastTcpErrorLogUtc = now;
                c.SuppressedTcpErrorLogs = 0;
                return;
            }

            c.SuppressedTcpErrorLogs++;
        }

        private async Task LoopUdp(DutLogHandler h, CancellationToken ct)
        {
            try
            {
                _udpClient = new UdpClient(UdpPort);
                _udpClient.Client.ReceiveTimeout = 1000;
                Hlog.I($"CommLogUDP listening on {UdpPort}");
                while (!ct.IsCancellationRequested)
                {
                    try
                    {
                        var res = await _udpClient.ReceiveAsync();
                        if (res.Buffer == null || res.Buffer.Length == 0)
                        {
                            continue;
                        }

                        string line;
                        try
                        {
                            line = Encoding.UTF8.GetString(res.Buffer).Trim('\0');
                        }
                        catch
                        {
                            continue;
                        }

                        if (string.IsNullOrWhiteSpace(line))
                        {
                            continue;
                        }

                        Hlog.I($"CommLogUDP recv {res.RemoteEndPoint} len={res.Buffer.Length}");

                        bool knownBoard = TryResolveBoard(res.RemoteEndPoint.Address.ToString(), out int team, out int group);
                        WriteUdpLog(res.RemoteEndPoint, team, group, res.Buffer, line);

                        if (!knownBoard)
                        {
                            continue;
                        }

                        if (TryParseDutLogPacket(line, out int dutId, out string txt))
                        {
                            _boardOnlineHandler?.Invoke(team, group, true);
                            AppendUdpDutLog(h, team, group, dutId, txt);
                        }
                    }
                    catch (SocketException)
                    {
                        await Task.Delay(50, ct);
                    }
                    catch (OperationCanceledException)
                    {
                        break;
                    }
                    catch (Exception ex)
                    {
                        Hlog.D($"CommLogUDP: {ex.Message}");
                        await Task.Delay(100, ct);
                    }
                }
            }
            catch (Exception ex)
            {
                Hlog.D($"CommLogUDP init: {ex.Message}");
            }
            finally
            {
                try { _udpClient?.Close(); } catch { }
                _udpClient = null;
            }
        }

        private bool TryParseDutLogPacket(string packet, out int dutId, out string text)
        {
            dutId = -1;
            text = null;
            if (string.IsNullOrEmpty(packet) || !packet.StartsWith("[DUT"))
            {
                return false;
            }

            int endBracket = packet.IndexOf(']');
            if (endBracket <= 4 || !int.TryParse(packet.Substring(4, endBracket - 4), out dutId))
            {
                return false;
            }

            text = packet.Substring(endBracket + 1);
            return true;
        }

        private void AppendUdpDutLog(DutLogHandler h, int team, int group, int dutId, string text)
        {
            string key = $"{team}:{group}:{dutId}";
            lock (_lineBufferLock)
            {
                if (!_udpLineBuffers.TryGetValue(key, out StringBuilder buffer))
                {
                    buffer = new StringBuilder();
                    _udpLineBuffers[key] = buffer;
                }

                if (buffer.Length > 0 && LooksLikeLogTokenStart(text))
                {
                    string partial = buffer.ToString().Trim('\0', '\r', '\n');
                    buffer.Clear();
                    if (!string.IsNullOrWhiteSpace(partial))
                    {
                        h(team, group, dutId, partial);
                    }
                }

                buffer.Append(text);
                FlushMalformedLeadingToken(h, team, group, dutId, buffer);

                while (true)
                {
                    int split = FindLineBreak(buffer);
                    if (split < 0)
                    {
                        break;
                    }

                    string line = buffer.ToString(0, split).Trim('\0', '\r');
                    int removeLen = split + 1;
                    if (removeLen < buffer.Length && buffer[split] == '\r' && buffer[removeLen] == '\n')
                    {
                        removeLen++;
                    }
                    buffer.Remove(0, removeLen);

                    if (!string.IsNullOrWhiteSpace(line))
                    {
                        h(team, group, dutId, line);
                    }
                }

                if (buffer.Length >= MaxBufferedLineLength)
                {
                    string partial = buffer.ToString().Trim('\0', '\r', '\n');
                    buffer.Clear();
                    if (!string.IsNullOrWhiteSpace(partial))
                    {
                        h(team, group, dutId, partial);
                    }
                }
            }
        }

        private void FlushMalformedLeadingToken(DutLogHandler h, int team, int group, int dutId, StringBuilder buffer)
        {
            if (buffer.Length < 3 || buffer[0] != '[')
            {
                return;
            }

            int secondStart = -1;
            for (int i = 1; i < buffer.Length; i++)
            {
                if (buffer[i] == ']')
                {
                    return;
                }
                if (buffer[i] == '[')
                {
                    secondStart = i;
                    break;
                }
            }

            if (secondStart <= 0)
            {
                return;
            }

            string partial = buffer.ToString(0, secondStart).Trim('\0', '\r', '\n');
            buffer.Remove(0, secondStart);
            if (!string.IsNullOrWhiteSpace(partial))
            {
                h(team, group, dutId, partial);
            }
        }

        private bool LooksLikeLogTokenStart(string text)
        {
            if (string.IsNullOrEmpty(text) || text[0] != '[')
            {
                return false;
            }

            int end = text.IndexOf(']');
            if (end <= 1 || end > 32)
            {
                return false;
            }

            for (int i = 1; i < end; i++)
            {
                char c = text[i];
                if (!(char.IsLetterOrDigit(c) || c == '_' || c == '-' || c == ' '))
                {
                    return false;
                }
            }
            return true;
        }

        private int FindLineBreak(StringBuilder buffer)
        {
            for (int i = 0; i < buffer.Length; i++)
            {
                if (buffer[i] == '\n' || buffer[i] == '\r')
                {
                    return i;
                }
            }
            return -1;
        }

        private void WriteUdpLog(IPEndPoint remoteEndPoint, int team, int group, byte[] buffer, string text)
        {
            try
            {
                string dir = Path.GetDirectoryName(_udpLogFilePath);
                if (!Directory.Exists(dir))
                {
                    Directory.CreateDirectory(dir);
                }

                string hex = BitConverter.ToString(buffer).Replace("-", " ");
                string line = $"{DateTime.Now:yyyy-MM-dd HH:mm:ss.fff} remote={remoteEndPoint} team={team} group={group} len={buffer.Length} text='{text}' hex={hex}";
                lock (_udpLogFileLock)
                {
                    File.AppendAllText(_udpLogFilePath, line + Environment.NewLine, Encoding.UTF8);
                }
            }
            catch (Exception ex)
            {
                Hlog.D($"CommLogUDP file write: {ex.Message}");
            }
        }

        private bool TryResolveBoard(string ip, out int team, out int group)
        {
            foreach (var kv in _map)
            {
                if (kv.Key == ip)
                {
                    team = kv.Value.T;
                    group = kv.Value.G;
                    return true;
                }
            }

            team = -1;
            group = -1;
            return false;
        }
    }
}
