using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using Hsg.Common;
using Hsg.BLL.Net;
using System.Net;
using Hsg.BLL;
using Hsg.BLL.TempCtr;
using Hsg.BLL.config;
using Hsg.BLL.Model;
using System.Threading;

namespace Test
{
    class Program
    {
        static int RecvLen = 0;
        static int SendLen = 0;
        static void StateMachineTest()
        {
            //HsgLogger logger = new HsgLogger();
            //StateDemo state = new StateDemo(logger);
            //state.Start(State.STATE_INI);
            //state.PostEventAsync(Event.Event_INI, null);
            //Task.Delay(5000).Wait();
            //while (true)
            //{
            //    Console.WriteLine("continue");
            //    state.PostEventAsync(Event.Event1, null);
            //    state.PostEventAsync(Event.Event2, null);
            //    // state.PostEventAsync(Event.Event3, null);
            //    //  Console.WriteLine("PostEvent start:" + Event.Event3);
            //    // bool ret = state.PostEvent(Event.Event3, null, 8000);
            //    //Console.WriteLine("PostEvent ret:" + ret);
            //    //   Task.Delay(10000).Wait();
            //    // Console.ReadKey();
            //}
        }

#if Test
        static async void UdpSend()
        {
            UdpSender sender = new UdpSender();
            int i = 10;
            byte[] data = new byte[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10,1, 2, 3, 4, 5, 6, 7, 8, 9, 10 };
            IPAddress ip = IPAddress.Parse("127.0.0.1");
            IPEndPoint ipEP = new IPEndPoint(ip, 10010);
            for (; i > 0; i--)
            {
                sender.SendData(data, ipEP);
                await Task.Delay(10);
            }
            SendLen = i * 10;
        }
        static void UdpTest()
        {
            UdpServer conn = new UdpServer(UdpRecvDataHandle);
            conn.start(10010);

            Task[] taskList = new Task[100];
            for (int i = 0; i < 100; i++)
            {
                taskList[i] = Task.Run(() => UdpSend());
            }
            Task.WaitAll(taskList);
        }
        static bool UdpRecvDataHandle(byte[] data, IPEndPoint ipEndPoint)
        {
            RecvLen += data.Length;
            Console.WriteLine("recv total:" + RecvLen);
            //Task.Delay(1).Wait();
            return true;
        }

        static void TempCtrTest()
        {
            int id = 0;
            while (true)
            {
                Console.WriteLine("input you connect id 0-50");
                string idStr =Console.ReadLine();
                if(int.TryParse(idStr,out id))
                {
                    if(id>=0&& id<50)
                    {
                        break;
                    }
                }
            }

            TempCtrBoardConfig cfg = new TempCtrBoardConfig(id);
            //cfg.IP = "192.168.50.3";
            //cfg.IP = "127.0.0.1";
            //cfg.Port = 64203;
            TempCtrBoardClient client = new TempCtrBoardClient(cfg, TempClientRecvHandle);
            client.StartConn();
            while (!client.Connected)
            {
                Console.WriteLine("Start wait connect ......");
                Task.Delay(1000).Wait();
            }
            Console.WriteLine("connected");
            while(true)
            {
                Console.WriteLine("input you choise on、st、sf、qt、qf 、qft");
               
                switch (Console.ReadLine())
                {
                    case "on":
                        if (client.SwitchOnTempCtr() == TempCtrRet.ok)
                        {
                            Console.WriteLine("set on");
                        }
                        break;
                    case "st":
                        if (client.SetTemp(85) == TempCtrRet.ok)
                        {
                            Console.WriteLine("set temp");
                        }
                        break;
                    case "sf":
                        if (client.SetFanSpeed(50) == TempCtrRet.ok)
                        {
                            Console.WriteLine("set fan");
                        }
                        break;
                    case "qt":
                        if (client.UpdateTemp() == TempCtrRet.ok)
                        {
                            Console.WriteLine("update temp");
                        }
                        break;
                    case "qf":
                        if (client.UpdateFanSpeed() == TempCtrRet.ok)
                        {
                            Console.WriteLine("update fan");
                        }
                        break;
                    case "qft":
                        if (client.QueryFault() == TempCtrRet.ok)
                        {
                            Console.WriteLine("update fan");
                        }
                        break;
                }
            }
           
        }
        static void TempClientRecvHandle(short cmdId, byte[]param)
        {
            float[] tempValue = new float[TempProtocol.ONE_TEAM_DUT_NUM];
            float[] compensator = new float[TempProtocol.ONE_TEAM_DUT_NUM];
            byte[] tempStatus = new byte[0];
            byte[] fanStatus = new byte[0];
            ushort[] SpeedVaule = new ushort[0];
            Console.WriteLine("recv resp");
            switch (cmdId)
            {
                case TempProtocol.CMD_ON_OFF:
                    Console.WriteLine("CMD_ON_OFF:");
                    foreach(var v in param)
                    {
                        Console.Write(v.ToString("D2"));
                    }
                    break;
                case TempProtocol.CMD_SET_TEMP:
                    Console.WriteLine("CMD_SET_TEMP:");
                    foreach (var v in param)
                    {
                        Console.Write(v.ToString("D2"));
                    }
                    break;
                case TempProtocol.CMD_SET_FAN_SPEED:
                    Console.WriteLine("CMD_SET_FAN_SPEED");
                    foreach (var v in param)
                    {
                        Console.Write(v.ToString("D2"));
                    }
                    break;
                case TempProtocol.CMD_QUERY_TEMP:
                     Console.WriteLine("CMD_QUERY_TEMP");
                    if(TempProtocol.DecodeTempParams(param, ref tempValue, compensator))
                    {
                        foreach(var v in tempValue)
                        {
                            Console.WriteLine(v);
                        }
                    }
                    break;
                case TempProtocol.CMD_QUERY_FAN_SPEED:
                    Console.WriteLine("CMD_QUERY_FAN_SPEED");
                    if(TempProtocol.DecodeFanParams(param, ref SpeedVaule))
                    {
                        foreach (var v in SpeedVaule)
                        {
                            Console.WriteLine(v);
                        }
                    }
                    break;
                case TempProtocol.CMD_QUERY_FAULT:
                    if (TempProtocol.DecodeQueryFaultParams(param, ref tempStatus, ref fanStatus))
                    {
                        Console.WriteLine("temp status");
                        foreach (var v in tempStatus)
                        {
                            Console.WriteLine(v);
                        }
                        Console.WriteLine("fan status");
                        foreach (var v in fanStatus)
                        {
                            Console.WriteLine(v);
                        }
                    }
                    break;
            }
        }

        static private void OnTempStateChange(TempCtrState state)
        {
            Console.WriteLine("new state:" + state);
        }
        static private void OnTempDutsStateChange(int id, TempCtrState state, float tempValue)
        {
            Console.WriteLine($"dut[{id}]new state:{state} value:{tempValue}");
        }
        static private void OnTempDutsValueChange(int id, float tempValue)
        {
            Console.WriteLine($"dut[{id}] value:{tempValue}");
        }
        static private void TempStateMachineTest()
        {
            TempCtrTeam tmpCtr = new TempCtrTeam(0, OnTempStateChange, OnTempDutsStateChange, OnTempDutsValueChange);
            tmpCtr.Run();
            while (true)
            {
                Console.WriteLine("input you choise st、 to、");

                switch (Console.ReadLine())
                {
                    case "st":
                        tmpCtr.StartWork();
                        break;
                    case "fr":
                        tmpCtr.ExitTestMode();
                        break;
                    case "to":
                        tmpCtr.WaitTempStabilityTimeout();
                        break;
                }
            }
        }
#endif
#if true

        static UInt32 count = 0;
        static private async Task MBClientTest(int i)
        {
            HsgCBCProtocol cbc = new Hsg.BLL.HsgCBCProtocol();
            int taskIndex = i;
            int count = 0;
            MBConfig _mbConfig = new MBConfig(i / 10, 0, null);
            Console.WriteLine("start test:" + i);
            cbc.StartConnect(_mbConfig);
            Console.WriteLine("mb conn task:" + i);
            while (count < 10000)
            {
                if (!cbc.ResetAllGpio() && i == 0)
                {
                    Console.WriteLine($"{taskIndex} {count}send failed");
                    count++;
                }
                await Task.Delay(100);
                if (!cbc.PowerSet(0xFFFF) && i == 0)
                {
                    Console.WriteLine($"{taskIndex} {count}send PowerSetfailed");
                    count++;
                }
                ushort setValue = 0;
                CBCProtocol.GroupIoCtrGetFlag((byte)EIOGroup.SWITCH_GROUP_MCU_PWR, true, out setValue, 12);
                if (!cbc.SetIOGroup((byte)EIOGroup.SWITCH_GROUP_MCU_PWR, setValue))
                {
                    Console.WriteLine($"{taskIndex} {count}send SetIOGroup failed");
                    count++;
                }
                await Task.Delay(100);
                CBCProtocol.GroupIoCtrGetFlag((byte)EIOGroup.SWITCH_GROUP_MCU_PWR, false, out setValue, 12);
                if (!cbc.SetIOGroup((byte)EIOGroup.SWITCH_GROUP_MCU_PWR, setValue))
                {
                    Console.WriteLine($"{taskIndex} {count}send SetIOGroup failed");
                    count++;
                }
                await Task.Delay(100);
                cbc.PowerChange(false, 1);
                if (!cbc.SyncPowerStatus() && i == 0)
                {
                    Console.WriteLine($"{taskIndex} {count}send SyncPowerStatus failed");
                    count++;
                }
                await Task.Delay(100);
                if (!cbc.PowerOffAll() && i == 0)
                {
                    Console.WriteLine($"{taskIndex} {count}send SyncPowerStatus failed");
                    count++;
                }
                await Task.Delay(100);
            }

        }
#endif
        #region  power set
        static private async Task PwrSet(HsgCBCProtocol cbc, uint id)
        {
            while (true)
            {
                //cbc.PowerChange(false, id);
                //await Task.Delay(2000);
                //cbc.SyncPowerStatus();
                Console.WriteLine("switch off");
                cbc.PowerSet(0xFFF);
                await Task.Delay(1000);
                //UInt16 flag = 0x02;
                //for(int i=0;i<12;i++)
                //{
                //    flag |=(UInt16) (1 << i);
                //    await Task.Delay(500);
                //    cbc.PowerSet(flag);
                //}
                cbc.SetIOGroup((ushort)EIOGroup.SWITCH_GROUP_MCU_PWR, 0x02);
                await Task.Delay(3000);
                cbc.SetIOGroup((ushort)EIOGroup.SWITCH_GROUP_MCU_PWR, 0xFFF);
                await Task.Delay(8000);
                cbc.PowerSet(0xF);
                await Task.Delay(3000);
                Console.WriteLine("swittch on");
            }

        }
        #endregion
        static  void Main(string[] args)
        {
            // UdpTest();
            //   TempCtrTest();
            //TempStateMachineTest();
            //int i = 0;
            //ThreadPool.SetMinThreads(200, 100);
            //while (i < 1)
            //{
            //    int value = i;
            //    Task.Run(async () => { await MBClientTest(value); });
            //    Console.WriteLine("init task" + i);
            //    i++;
            //}
            MBConfig _mbConfig = new MBConfig(0, 0, null);
            Console.WriteLine("start test");
            HsgCBCProtocol cbc = new Hsg.BLL.HsgCBCProtocol();
            cbc.StartConnect(_mbConfig);
            uint i = 0;
            uint value = i;
            Task.Run(async () => { await PwrSet(cbc, value); });
            Console.WriteLine("init task" + i);
            i++;
            //while (i < 1)
            //{
                
            //}
            Console.Read();
            while (true)
            {
                Task.Delay(1000).Wait();
                Console.WriteLine("wait...");
            }

        }
    }
}
