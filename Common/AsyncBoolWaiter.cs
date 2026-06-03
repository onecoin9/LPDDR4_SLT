using System;
using System.Collections.Concurrent;
using System.Threading;
using System.Threading.Tasks;

public class TaskWaiter
{
    //private int _lastRequestSerial;
    //private int _pickRequestSerial;
    private readonly object _lock = new object();
    private Semaphore _taskSem = new Semaphore(0, 1);
    public void SetTaskDone()
    {
        lock (_lock)
        {
            // 检查任务序列号是否匹配
            //if (_pickRequestSerial == _lastRequestSerial)
            //{
            //    // 释放信号量，通知任务完成

            //}
            _taskSem.WaitOne(0);
            _taskSem.Release();
        }
    }
    //public void PickTask()
    //{
    //    lock (_lock)
    //    {
    //        _pickRequestSerial =  _lastRequestSerial;
    //    }
    //}
    public bool WaitTaskDone(int timeoutMilliseconds)
    {
        lock (_lock)
        {
            _taskSem.WaitOne(0);
        }
        return _taskSem.WaitOne(timeoutMilliseconds);
    }
}

//// 使用示例
//public class Program
//{
//    public static async Task Main(string[] args)
//    {
//        var waiter = new AsyncBoolWaiter();

//        // 启动一个任务来改变Flag的值
//        Task.Run(() =>
//        {
//            Thread.Sleep(3000); // 模拟一些操作
//            waiter.Flag = true;
//        });

//        // 等待Flag变为true，超时时间为5000毫秒
//        bool result = await waiter.WaitForFlagToBecomeTrueAsync(5000);

//        Console.WriteLine($"Flag变为true了吗？{result}");
//    }
//}