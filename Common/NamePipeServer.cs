using System;
using System.Collections.Generic;
using System.IO.Pipes;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common
{
    public delegate void OnRecvPipeMsgHandle(string msg);
    public delegate void OnPipeStateChange(bool isReady);
    public class NamePipeServer
    {
        private string _pipeName;
        private NamedPipeServerStream _serverPipe;
        private bool _available;
        private const int readTimeout = 1000;
        private const int writeTimeout = 1000;
        public bool Available { get { return _available; } }
        // private readonly object _sndLock = new object();
        private bool _exit = false;
        public OnRecvPipeMsgHandle OnRecvMsgHandle;
        public OnPipeStateChange OnPipeStateChange;
        public NamePipeServer(string name)
        {
            _pipeName = name;
            _serverPipe = new NamedPipeServerStream(name, PipeDirection.InOut, 1, PipeTransmissionMode.Byte, PipeOptions.Asynchronous);
            if (_serverPipe.CanTimeout)
            {
                _serverPipe.ReadTimeout = readTimeout;
                _serverPipe.WriteTimeout = writeTimeout;
            }
        }
        public async void StartService()
        {
            _exit = false;
            await Task.Run(async () =>
            {
                byte[] buffer = new byte[1024];
                while (!_exit)
                {
                    _serverPipe.WaitForConnection();
                    OnPipeStateChange?.Invoke(true);
                    // _clientPipe.ReadTimeout = readTimeout;
                    _available = true;
                    //Console.WriteLine("pipe server connect.");
                    Hlog.D("PipeSvr", $"pipe server connect");
                    int bytesRead;
                    try
                    {
                        while ((bytesRead = await _serverPipe.ReadAsync(buffer, 0, buffer.Length)) != 0)
                        {
                            string message = Encoding.UTF8.GetString(buffer, 0, bytesRead);
                           // Console.WriteLine($"Received message from client: {message}");
                            Hlog.D("PipeSvr",$"Received message from client: {message}");
                            OnRecvMsgHandle?.Invoke(message);
                        }
                    }
                    catch
                    {

                    }
                    finally
                    {
                        _serverPipe.Disconnect();
                        Hlog.D("PipeSvr", $"pipe disconnect");
                    }
                    OnPipeStateChange?.Invoke(false);
                }
            }).ConfigureAwait(false);
        }

        public void StopService()
        {
            _exit = true;
            try
            {
                _serverPipe.Disconnect();
            }catch
            {

            }
            
        }
    }
}
