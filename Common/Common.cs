using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
namespace Hsg.Common
{
    public enum LOG_TYPE
    {
        INFO,//信息
        DONE,//执行成功
        ERROR,//错误 
        WARNNING,//测试请求 
    }
    public delegate void IUIAppendLog(string log, LOG_TYPE logType);

    public delegate bool IUpdateUILayer<T>(T status);
    public delegate bool ICommunicateChannel<T1, T2>(T1 evt, T2 param);
    public delegate bool IRecvDataHandle(byte[] data);

    /// <summary>
    /// 业务沟通接口
    /// </summary>
    /// <typeparam name="T1">事件</typeparam>
    /// <typeparam name="T2">参数</typeparam>
    public interface IBSHandler<T1, T2>
    {
        /// <summary>
        /// 用于外部调用，与内部沟通
        /// </summary>
        /// <param name="evt"></param>
        /// <param name="param"></param>
        /// <returns></returns>
        bool InputEventInterface(T1 evt, T2 param);
    }
    public enum ConnState
    {
        DISCONNECT,// 未连接
        CONNECTED,//  已经连接
    }
    public enum TestStage
    {
        ST_NOT_START,// 未启动
        ST_PREPARE,// 准备中
        ST_READY,// 准备就绪
        ST_TESTING,// 测试中
        ST_TEST_FAIL,// 测试失败
        ST_TEST_SUCCESS,// 测试成功
        ST_TEST_TIMEOUT//测试超时
    }
    public enum WorkMode
    {
        OffLine,
        Online,
        Slave,// 从机模式
        Debug
    }
}

