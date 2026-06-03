using Hsg.BLL;
using Hsg.BLL.config;
using Hsg.BLL.Model;
using Hsg.BLL.Service;
using Hsg.Common;
using Hsg.Common.ADO;
using System;
using System.IO;
using System.Threading;
using System.Windows.Forms;
namespace Hsg.View
{
    static class Program
    {
        /// <summary>
        /// 应用程序的主入口点。
        /// </summary>
        [STAThread]
        static void Main(String[] args)
        {
            bool createdNew;
            bool slaveLaunch = false;
            Mutex mutex = new Mutex(true, "MyMutex", out createdNew);
            if (args.Length > 0)
            {
                slaveLaunch = true;
            }
            if (!createdNew && !slaveLaunch)
            {
                MessageBox.Show("程序已经启动，请勿重复运行");
                return;
            }
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            // 创建线程池  
            bool result = ThreadPool.SetMinThreads(400, 100);
            if (!result)
            {
                MessageBox.Show("系统资源不足可能引起程序卡顿");
            }
            if (!Directory.Exists(SysConfig.PolicyFolderPath))
            {
                Directory.CreateDirectory(SysConfig.PolicyFolderPath);
            }
            if (args.Length > 0)// 从机模式检查接MES
            {
                string errorMsg = "";
                string tsName = "";
                MesClientService msClient = MesClientService.GetInstance();
                string frameVer = typeof(MainForm).Assembly.GetName().Version.ToString();
                string libVer = typeof(BSController).Assembly.GetName().Version.ToString();
                msClient.RegistSystemVersion(frameVer, libVer);
                msClient.Run();
                SlaveModeConfig cfg = SlaveModeConfig.LoadConfig(args[0], ref tsName, ref errorMsg);
                if (cfg == null)
                {
                    msClient.OnLaunchError(errorMsg);
                    MessageBox.Show("配置文件错误:" + errorMsg);
                    Application.Exit();
                }
                else if (!createdNew)
                {
                    errorMsg = "Open faile,Program is repeat open.";
                    msClient.OnLaunchError(errorMsg);
                    MessageBox.Show("程序已经启动，请勿重复运行");
                    return;
                }
                else
                {
                    DBHandler _dbHdr = DBHandler.Instance;
                    if (!_dbHdr.LoadDataBase())
                    {
                        errorMsg = "db file load fail.";
                        msClient.OnLaunchError(errorMsg);
                        MessageBox.Show("载入数据库失败");
                        return;
                    }
                    string workStageDescript = "";
                    string workStageName = "";
                    if (!WorkStage.GetStageInfo(cfg.ProcessesId, ref workStageName, ref workStageDescript))
                    {
                        errorMsg = "ProcessesId is valid.";
                        msClient.OnLaunchError(errorMsg);
                        MessageBox.Show($"工序参数错误：{cfg.ProcessesId}");
                        return;
                    }
                    switch (cfg.ProcessesId)
                    {
                        case 0:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, true, true, cfg.TSPath);
                            break;
                        case 1:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, false, true, cfg.TSPath);
                            break;
                        case 2:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, false, false, cfg.TSPath);
                            break;
                        case 3:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, true, false, cfg.TSPath);
                            break;
                        case 4:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, false, false, cfg.TSPath);
                            break;
                        case 5:
                            SysConfig.SetWorkOrderDetail(WorkMode.Slave, workStageDescript, workStageName, 0, cfg.WorkOrderNo, cfg.OrderNo, cfg.MaterialNo, (byte)cfg.TempState, false, false, cfg.TSPath);
                            break;
                    }
                    msClient.LoadConfigInfor(cfg, tsName);
                    MainForm mainForm = new MainForm();
                    mainForm.Is_DebugMode = false;
                    msClient.ICloseMainWnd = mainForm.ReqCloseWindow;
                    Application.Run(mainForm);
                }
            }
            else
            {
                ModeSelect modeChoiseDlg = new ModeSelect();
                DBHandler _dbHdr = DBHandler.Instance;
                if (!_dbHdr.LoadDataBase())
                {
                    MessageBox.Show("载入数据库失败");
                    return;
                }
                if (modeChoiseDlg.ShowDialog() == DialogResult.OK)
                {
                    bool debugMode = (SysConfig.WorkMode == WorkMode.Debug);
                    MainForm mainForm = new MainForm();
                    mainForm.Is_DebugMode = debugMode;
                    Application.Run(mainForm);
                }
            }


            mutex.ReleaseMutex();
            mutex.Dispose();

        }
    }
}
