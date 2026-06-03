using System;
using System.Collections.Generic;
using System.Data;
using System.Data.SQLite;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace Hsg.Common.ADO
{
    public class DBHandler
    {
        private SQLiteConnection _connection;
        private string m_ConnStr = @"DataSource = HGProduction.db; Version=3";
        public static DBHandler Instance = new DBHandler();
        private static readonly object _opLock = new object();
        private DBHandler()
        {
        }
        //public bool ConnectionTest()
        //{
        //    return SQLiteHelper.ConnectionTest(m_ConnStr);
        //}
        public bool LoadDataBase()
        {
            if (_connection?.State == ConnectionState.Open)
            {
                return true;
            }
            try
            {
                _connection = new SQLiteConnection(m_ConnStr);
                _connection.Open();
                //  _connection.ChangePassword("www.hosinglobal.com");
            }
            catch (Exception ex)
            {
                Console.WriteLine("ex:", ex.Message);
                return false;
            }

            if (_connection.State == ConnectionState.Open)
            {
                CheckWorkStateTable();
                CheckDutLastStateTable();
                CheckComponentAbnormalRecordTable();
                CheckWorkOrderTable();
                return true;
            }
            return false;
        }
        // workOrderStage
        public DataSet QueryWorkStageFromTable()
        {
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand cmd = SQLiteHelper.CreateCommand(_connection, "select * from workStage", null))
            {
                try
                {
                    return SQLiteHelper.ExecuteDataset(cmd);
                }
                catch/* (Exception ex)*/
                {
                    return null;
                }
            }
        }
        private void CheckWorkStateTable()
        {
            string updateQuery =
                               @"WITH total_count AS (
                                    SELECT COUNT(*) AS cnt FROM workStage
                                )
                                UPDATE workStage
                                SET 
                                    description = CASE id
                                        WHEN 0 THEN '首测(单站)'
                                        WHEN 1 THEN '终测'
                                        WHEN 2 THEN '复测-1'
                                    END,
                                    addPass = CASE id
                                        WHEN 0 THEN TRUE
                                        WHEN 1 THEN TRUE
                                        WHEN 2 THEN FALSE
                                    END
                                WHERE id IN (0, 1, 2)
                                AND (SELECT cnt FROM total_count) < 4;";
            string insertQuery =
                                @"INSERT INTO workStage (id, name, description, addTotal, addPass)
                                    SELECT 3, 'MFT', '首测(多站)', TRUE, FALSE
                                    WHERE NOT EXISTS (SELECT 1 FROM workStage WHERE id = 3)
                                    UNION
                                    SELECT 4, 'PRT2', '复测-2', FALSE, FALSE
                                    WHERE NOT EXISTS (SELECT 1 FROM workStage WHERE id = 4)
                                    UNION
                                    SELECT 5, 'PRT3', '复测-3', FALSE, FALSE
                                    WHERE NOT EXISTS (SELECT 1 FROM workStage WHERE id = 5);";
            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }

                // 更新操作
                using (SQLiteCommand updateCommand = new SQLiteCommand(updateQuery, _connection))
                {
                    try
                    {
                        int exeUpdate = updateCommand.ExecuteNonQuery();
                        Console.WriteLine($"更新成功，影响行数：{exeUpdate}");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"更新失败：{ex.Message}");
                    }
                }

                // 插入操作
                using (SQLiteCommand insertCommand = new SQLiteCommand(insertQuery, _connection))
                {
                    try
                    {
                        int exeInsert = insertCommand.ExecuteNonQuery();
                        Console.WriteLine($"插入成功，影响行数：{exeInsert}");
                    }
                    catch (Exception ex)
                    {
                        Console.WriteLine($"插入失败：{ex.Message}");
                    }
                }
                _connection.Close();
            }

        }
        // workOrder 工单管理
        public void CheckWorkOrderTable()
        {
            string tableName = "workOrder";

            string checkTableQuery = $"SELECT name FROM sqlite_master WHERE type='table' AND name='{tableName}';";
            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, checkTableQuery, null))
                {
                    object result = command.ExecuteScalar();

                    if (result == null)
                    {
                        // 表格不存在，创建表格
                        string createTableQuery = $@"CREATE TABLE workOrder (
                                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                                    orderNo VARCHAR(32) NOT NULL,
                                                    materialNo VARCHAR(32) NOT NULL,
                                                    workOrderNo VARCHAR(32) NOT NULL,
                                                    workStageId INT NOT NULL,
                                                    policyName VARCHAR(128),
                                                    cfgDescription  VARCHAR(256),
                                                    closed BOOLEAN DEFAULT FALSE,
                                                    createTime DATETIME DEFAULT(datetime('now')),
                                                    UNIQUE(orderNo, workOrderNo),
                                                    FOREIGN KEY(workStageId) REFERENCES WorkStage(id)
                                                ); "; 
                        using (SQLiteCommand createCommand = new SQLiteCommand(createTableQuery, _connection))
                        {
                            createCommand.ExecuteNonQuery();
                            // Console.WriteLine("表格 error_table 创建成功！");
                        }
                    }
                }
            }

        }
        public bool InsertRecordToWorkOrderTable(string orderNo, string materialNo, 
                                                string workOrderNo, int workStageId, 
                                                string policyName, byte tmpState)
        {
            string commandString = "INSERT INTO workOrder (orderNo, materialNo, workOrderNo, workStageId, policyName,tmpState) "
                                   + "VALUES (@orderNo, @materialNo, @workOrderNo, @workStageId, @policyName, @tmpState)";
            SQLiteParameter[] commandParameters = new SQLiteParameter[]
             {
                new SQLiteParameter( "@orderNo",DbType.String),
                new SQLiteParameter( "@materialNo", DbType.String),
                new SQLiteParameter( "@workOrderNo",DbType.String),
                new SQLiteParameter( "@workStageId",DbType.Int32,4),
                new SQLiteParameter( "@policyName", DbType.String),
                new SQLiteParameter( "@tmpState", DbType.Byte)
             };

            commandParameters[0].Value = orderNo;
            commandParameters[1].Value = materialNo;
            commandParameters[2].Value = workOrderNo;
            commandParameters[3].Value = workStageId;
            commandParameters[4].Value = policyName;
            commandParameters[5].Value = tmpState;
            if (_connection == null)
            {
                return false;
            }
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, commandString, commandParameters))
            {
                try
                {
                    return command.ExecuteNonQuery() == 1;
                }
                catch (Exception ex)
                {
                    Console.WriteLine("ex:" + ex.Message);
                }
                return false;
            }
        }

        public DataSet QueryWorkOrderView()
        {
            string queryCmdString = "select workStageId,workStageName,workStageDescription,addTotal,addPass,workOrderId,orderNo,materialNo,workOrderNo,policyName,tmpState,createTime from workOrderView where closed=false;";
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand cmd = SQLiteHelper.CreateCommand(_connection, queryCmdString, null))
            {
                try
                {

                    return SQLiteHelper.ExecuteDataset(cmd);
                }
                catch/* (Exception ex)*/
                {
                    return null;
                }

            }
        }

        public bool DeleteWorkOrder(int workOrderId)
        {
            string deleteSqlString = $"delete from workOrder where id={workOrderId}";
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand cmd = SQLiteHelper.CreateCommand(_connection, deleteSqlString, null))
            {
                try
                {
                    return SQLiteHelper.ExecuteNonQuery(cmd) == 1;
                }
                catch /*(Exception ex)*/
                {
                    return false;
                }
            }
        }

        public bool CloseWorkOrder(int workOrderId)
        {
            string deleteSqlString = $"update workOrder set closed=TRUE where id={workOrderId}";
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand cmd = SQLiteHelper.CreateCommand(_connection, deleteSqlString, null))
            {
                try
                {
                    return SQLiteHelper.ExecuteNonQuery(cmd) == 1;
                }
                catch/* (Exception ex)*/
                {
                    return false;
                }
            }
        }

        public bool QueryWorkOrderInfor(int workOrderId, ref string orderNo, ref string materialNo,
                                    ref string workOrderNo,ref string policyName)
        {
            string queryString = $"select orderNo,materialNo,workOrderNo,policyName from workOrder where id={workOrderId}";
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            using (SQLiteCommand cmd = SQLiteHelper.CreateCommand(_connection, queryString, null))
            {
                try
                {
                    IDataReader reader = SQLiteHelper.ExecuteReader(cmd, queryString, null);
                    while (reader.Read())
                    {
                        // 处理查询结果
                        //int id = reader.GetInt32(reader.GetOrdinal("id"));
                        orderNo = reader.GetString(reader.GetOrdinal("orderNo"));
                        materialNo = reader.GetString(reader.GetOrdinal("materialNo"));
                        workOrderNo = reader.GetString(reader.GetOrdinal("workOrderNo"));
                        policyName = reader.GetString(reader.GetOrdinal("policyName"));
                        break;
                    }

                    reader.Close(); // 完成后关闭reader
                }
                catch/* (Exception ex)*/
                {
                    return false;
                }
            }

            return true;
        }

        public bool UpdateDutLastStateCode(int boxId, int dutId, short stateCode)
        {
            string updateCmd = $"INSERT INTO lastState(boxId, dutId, lastCode, count, updateTime) VALUES({boxId}, {dutId}, {stateCode},1, datetime('now'))" +
                @" ON CONFLICT(boxId, dutId) DO UPDATE SET
                    lastCode = excluded.lastCode,
                    count = 1,
                    updateTime = excluded.updateTime
                WHERE
                lastState.lastCode <> excluded.lastCode; ";
            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            try
            {
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, updateCmd, null))
                {
                    int result = command.ExecuteNonQuery();
                    return result > 0;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("ex:" + ex.Message);
            }

            return false;
        }
        public bool UpdateDutLastStateCodeCount(int boxId, int dutId, short stateCode, short count)
        {
            string updateCmd = $"UPDATE  lastState set count = {count} where  boxId = {boxId} and dutId = {dutId} and lastCode = {stateCode};";
            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                try
                {
                    using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, updateCmd, null))
                    {
                        int result = command.ExecuteNonQuery();
                        return result > 0;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("ex:" + ex.Message);
                }
            }

            return false;
        }
        public void CheckDutLastStateTable()
        {
            string tableName = "lastState";

            string checkTableQuery = $"SELECT name FROM sqlite_master WHERE type='table' AND name='{tableName}';";
            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, checkTableQuery, null))
                {
                    object result = command.ExecuteScalar();

                    if (result == null)
                    {
                        // 表格不存在，创建表格
                        string createTableQuery = "CREATE TABLE lastState (  id INTEGER PRIMARY KEY AUTOINCREMENT,  boxId INTEGER,  dutId INTEGER,  lastCode SHORT DEFAULT 0, count SHORT DEFAULT 1, updateTime DATETIME DEFAULT(datetime('now')),  UNIQUE (boxId, dutId)  ); ";
                        using (SQLiteCommand createCommand = new SQLiteCommand(createTableQuery, _connection))
                        {
                            createCommand.ExecuteNonQuery();
                            // Console.WriteLine("表格 error_table 创建成功！");
                        }
                    }
                }
            }
        }

        public void QueryDutsLastStateCode(int boxId, ref short[] stateCodes, ref short[] continueCounts)
        {
            lock (_opLock)
            {
                string checkTableQuery = $"select dutId,lastCode,count from lastState where boxId={boxId};";
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, checkTableQuery, null))
                {
                    IDataReader reader = SQLiteHelper.ExecuteReader(command, checkTableQuery, null);
                    while (reader.Read())
                    {
                        int index = reader.GetInt32(reader.GetOrdinal("dutId"));
                        if (index >= 0 && index < stateCodes.Length)
                        {
                            stateCodes[index] = reader.GetInt16(reader.GetOrdinal("lastCode"));
                            continueCounts[index] = reader.GetInt16(reader.GetOrdinal("count"));
                        }
                    }
                    reader.Close();
                }
            }

        }

        /// <summary>
        /// 用于记录温控异常和通讯板异常
        /// </summary>
        public void CheckComponentAbnormalRecordTable()
        {
            string tableName = "abnormalRecord";

            string checkTableQuery = $"SELECT name FROM sqlite_master WHERE type='table' AND name='{tableName}';";
            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, checkTableQuery, null))
                {
                    object result = command.ExecuteScalar();

                    if (result == null)
                    {
                        // 表格不存在，创建表格
                        string createTableQuery = "CREATE TABLE abnormalRecord (  id INTEGER PRIMARY KEY AUTOINCREMENT,  boxId INTEGER,  componentId INTEGER, abnormalCode SHORT DEFAULT 0, count SHORT DEFAULT 1, extraInfo varchar  DEFAULT NULL, updateTime DATETIME DEFAULT(datetime('now')),  UNIQUE (boxId, componentId, abnormalCode)  ); ";
                        using (SQLiteCommand createCommand = new SQLiteCommand(createTableQuery, _connection))
                        {
                            createCommand.ExecuteNonQuery();
                            // Console.WriteLine("表格 error_table 创建成功！");
                        }
                    }
                }
            }
        }

        public bool AddComponentNewAbnormalRecord(int boxId, int componentId, short abnormalCode, string extraInfo)
        {
            string updateCmd = "";
            if (extraInfo == null)
            {
                updateCmd = $"INSERT INTO abnormalRecord(boxId, componentId, abnormalCode, count, updateTime) VALUES({boxId}, {componentId}, {abnormalCode},1, datetime('now'))" +
               @" ON CONFLICT(boxId, componentId, abnormalCode) DO UPDATE SET
                    count = count+1,
                    updateTime = excluded.updateTime; ";
            }
            else
            {
                updateCmd = $"INSERT INTO abnormalRecord(boxId, componentId, abnormalCode, extraInfo, count, updateTime) VALUES({boxId}, {componentId}, {abnormalCode},'{extraInfo}',1, datetime('now'))" +
               @" ON CONFLICT(boxId, componentId, abnormalCode) DO UPDATE SET
                    count = count+1,
                    extraInfo = excluded.extraInfo,
                    updateTime = excluded.updateTime; ";
            }

            if (_connection.State == ConnectionState.Closed)
            {
                _connection.Open();
            }
            try
            {
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, updateCmd, null))
                {
                    int result = command.ExecuteNonQuery();
                    return result > 0;
                }
            }
            catch (Exception ex)
            {
                Console.WriteLine("ex:" + ex.Message);
            }

            return false;
        }
        public bool DeleteComponentAbnormalRecord(int boxId, int componentId, short abnormalCode)
        {
            string deleteCmd = "";

            deleteCmd = $"Delete from abnormalRecord where boxId = {boxId} and componentId = {componentId} and abnormalCode={abnormalCode};";

            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                try
                {
                    using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, deleteCmd, null))
                    {
                        int result = command.ExecuteNonQuery();
                        return result > 0;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("ex:" + ex.Message);
                }
            }

            return false;
        }
        public bool DeleteComponentAbnormalRecord(int boxId)
        {
            string deleteCmd = "";

            deleteCmd = $"Delete from abnormalRecord where boxId = {boxId};";

            lock (_opLock)
            {
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                try
                {
                    using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, deleteCmd, null))
                    {
                        int result = command.ExecuteNonQuery();
                        return result > 0;
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine("ex:" + ex.Message);
                }
            }

            return false;
        }

        public void QueryComponentAbnormalRecord(int boxId, ref List<AbnormalRecord> readRecord)
        {
            lock (_opLock)
            {
                string checkTableQuery = $"select componentId,abnormalCode,count,extraInfo from abnormalRecord where boxId={boxId};";
                if (_connection.State == ConnectionState.Closed)
                {
                    _connection.Open();
                }
                using (SQLiteCommand command = SQLiteHelper.CreateCommand(_connection, checkTableQuery, null))
                {
                    IDataReader reader = SQLiteHelper.ExecuteReader(command, checkTableQuery, null);
                    //abnormalCodes = new short[reader.FieldCount];
                    //count = new short[reader.FieldCount];
                    //extraDetails = new string[reader.FieldCount];
                    // List<AbnormalRecord> readRecord = new List<AbnormalRecord>();
                    while (reader.Read())
                    {
                        int index = reader.GetInt32(reader.GetOrdinal("componentId"));
                        if (index >= 0)
                        {
                            AbnormalRecord record = new AbnormalRecord();
                            record.id = index;
                            record.code = reader.GetInt16(reader.GetOrdinal("abnormalCode"));
                            record.count = reader.GetInt16(reader.GetOrdinal("count"));
                            string extraInfo = string.Empty;
                            try
                            {
                                extraInfo = reader.GetString(reader.GetOrdinal("extraInfo"));
                            }
                            catch
                            {

                            }
                            record.extra = extraInfo;
                            readRecord.Add(record);
                        }
                    }
                    reader.Close();
                    // return SQLiteHelper.ExecuteDataset(command);
                }
            }

        }
    }
}
