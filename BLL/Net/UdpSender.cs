using System;
using System.Collections.Generic;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.BLL.Net
{
    public class UdpSender
    {
        private UdpClient _sender;
        private UdpServer _udpConn;
        private const int  UDP_MAX_PBUF = 512 - 42; // 因为通讯板限制了最大的数据报文长度PBUF为512,除去包头(MAC头14+IP头20+TCP头8）包头 42
        private Object _sndLock = new object();
        public UdpSender()
        {
            _sender = new UdpClient();
        }
        public UdpSender(UdpServer connClient)
        {
            _udpConn = connClient;
        }
        public UdpSender(UInt16 sendPort)
        {
            _sender = new UdpClient(sendPort);
        }
        private int ToSend(byte[] data, int bytes, IPEndPoint ip)
        {
            if (_sender != null)
            {
                return _sender.Send(data, bytes, ip);
            }
            if (_udpConn != null)
            {
                return _udpConn.SendData(data, bytes, ip);
            }
            return 0;
        }
        public int SendData(byte[] data, IPEndPoint point)
        {
            //IPEndPoint point = new IPEndPoint(IPAddress.Parse(Ip), Int32.Parse(txPort));
            Int32 totalLen = data.Length;
            int ret = 0;
            int sndLen = 0;
            int offset = 0;
            byte[] sndTmp = new byte[UDP_MAX_PBUF];
            lock(_sndLock)
            {
                while (totalLen > 0)
                {
                    sndLen = totalLen > UDP_MAX_PBUF ? UDP_MAX_PBUF : totalLen;
                    Array.Copy(data, offset, sndTmp, 0, sndLen);
                    ret = ToSend(sndTmp, sndLen, point);
                    if (ret > 0)
                    {
                        offset += sndLen;
                        totalLen -= ret;
                    }
                    else
                    {
                        break;
                    }
                }
            }
            return 0;
        }
        public void Close()
        {
            if (_sender != null)
            {
                _sender.Close();
                _sender = null;
            }
        }
    }
}
