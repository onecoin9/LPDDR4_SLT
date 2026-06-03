namespace Hsg.View
{
    partial class WorkOrderAddDlg
    {
        /// <summary>
        /// Required designer variable.
        /// </summary>
        private System.ComponentModel.IContainer components = null;

        /// <summary>
        /// Clean up any resources being used.
        /// </summary>
        /// <param name="disposing">true if managed resources should be disposed; otherwise, false.</param>
        protected override void Dispose(bool disposing)
        {
            if (disposing && (components != null))
            {
                components.Dispose();
            }
            base.Dispose(disposing);
        }

        #region Windows Form Designer generated code

        /// <summary>
        /// Required method for Designer support - do not modify
        /// the contents of this method with the code editor.
        /// </summary>
        private void InitializeComponent()
        {
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(WorkOrderAddDlg));
            this.label2 = new System.Windows.Forms.Label();
            this.m_txb_orderNo = new System.Windows.Forms.TextBox();
            this.label3 = new System.Windows.Forms.Label();
            this.m_txb_materialNo = new System.Windows.Forms.TextBox();
            this.label4 = new System.Windows.Forms.Label();
            this.label7 = new System.Windows.Forms.Label();
            this.m_btn_ok = new System.Windows.Forms.Button();
            this.m_btn_cancel = new System.Windows.Forms.Button();
            this.label1 = new System.Windows.Forms.Label();
            this.m_cbx_stage = new System.Windows.Forms.ComboBox();
            this.m_txt_policy_path = new System.Windows.Forms.TextBox();
            this.m_btn_policy_choise = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // label2
            // 
            this.label2.AutoSize = true;
            this.label2.Location = new System.Drawing.Point(19, 62);
            this.label2.Name = "label2";
            this.label2.Size = new System.Drawing.Size(135, 24);
            this.label2.TabIndex = 0;
            this.label2.Text = "订单编号：";
            // 
            // m_txb_orderNo
            // 
            this.m_txb_orderNo.Font = new System.Drawing.Font("Arial", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.m_txb_orderNo.Location = new System.Drawing.Point(118, 57);
            this.m_txb_orderNo.Name = "m_txb_orderNo";
            this.m_txb_orderNo.Size = new System.Drawing.Size(472, 35);
            this.m_txb_orderNo.TabIndex = 1;
            // 
            // label3
            // 
            this.label3.AutoSize = true;
            this.label3.Location = new System.Drawing.Point(19, 102);
            this.label3.Name = "label3";
            this.label3.Size = new System.Drawing.Size(135, 24);
            this.label3.TabIndex = 0;
            this.label3.Text = "物料编号：";
            // 
            // m_txb_materialNo
            // 
            this.m_txb_materialNo.Font = new System.Drawing.Font("Arial", 12F, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, ((byte)(0)));
            this.m_txb_materialNo.Location = new System.Drawing.Point(118, 97);
            this.m_txb_materialNo.Name = "m_txb_materialNo";
            this.m_txb_materialNo.Size = new System.Drawing.Size(472, 35);
            this.m_txb_materialNo.TabIndex = 2;
            // 
            // label4
            // 
            this.label4.AutoSize = true;
            this.label4.Location = new System.Drawing.Point(19, 25);
            this.label4.Name = "label4";
            this.label4.Size = new System.Drawing.Size(0, 24);
            this.label4.TabIndex = 0;
            // 
            // label7
            // 
            this.label7.AutoSize = true;
            this.label7.Location = new System.Drawing.Point(19, 146);
            this.label7.Name = "label7";
            this.label7.Size = new System.Drawing.Size(135, 24);
            this.label7.TabIndex = 0;
            this.label7.Text = "测试方案：";
            // 
            // m_btn_ok
            // 
            this.m_btn_ok.Location = new System.Drawing.Point(153, 225);
            this.m_btn_ok.Name = "m_btn_ok";
            this.m_btn_ok.Size = new System.Drawing.Size(113, 47);
            this.m_btn_ok.TabIndex = 8;
            this.m_btn_ok.Text = "确定";
            this.m_btn_ok.UseVisualStyleBackColor = true;
            this.m_btn_ok.Click += new System.EventHandler(this.m_btn_ok_Click);
            // 
            // m_btn_cancel
            // 
            this.m_btn_cancel.Location = new System.Drawing.Point(364, 225);
            this.m_btn_cancel.Name = "m_btn_cancel";
            this.m_btn_cancel.Size = new System.Drawing.Size(113, 47);
            this.m_btn_cancel.TabIndex = 9;
            this.m_btn_cancel.Text = "取消";
            this.m_btn_cancel.UseVisualStyleBackColor = true;
            this.m_btn_cancel.Click += new System.EventHandler(this.m_btn_cancel_Click);
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(19, 20);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(135, 24);
            this.label1.TabIndex = 0;
            this.label1.Text = "工序选择：";
            // 
            // m_cbx_stage
            // 
            this.m_cbx_stage.DropDownStyle = System.Windows.Forms.ComboBoxStyle.DropDownList;
            this.m_cbx_stage.FormattingEnabled = true;
            this.m_cbx_stage.Location = new System.Drawing.Point(118, 17);
            this.m_cbx_stage.Name = "m_cbx_stage";
            this.m_cbx_stage.Size = new System.Drawing.Size(472, 32);
            this.m_cbx_stage.TabIndex = 0;
            // 
            // m_txt_policy_path
            // 
            this.m_txt_policy_path.Location = new System.Drawing.Point(118, 143);
            this.m_txt_policy_path.Name = "m_txt_policy_path";
            this.m_txt_policy_path.ReadOnly = true;
            this.m_txt_policy_path.Size = new System.Drawing.Size(472, 35);
            this.m_txt_policy_path.TabIndex = 17;
            // 
            // m_btn_policy_choise
            // 
            this.m_btn_policy_choise.Location = new System.Drawing.Point(596, 143);
            this.m_btn_policy_choise.Name = "m_btn_policy_choise";
            this.m_btn_policy_choise.Size = new System.Drawing.Size(74, 29);
            this.m_btn_policy_choise.TabIndex = 16;
            this.m_btn_policy_choise.Text = "选择";
            this.m_btn_policy_choise.UseVisualStyleBackColor = true;
            this.m_btn_policy_choise.Click += new System.EventHandler(this.OnPolicySelectBtnClick);
            // 
            // WorkOrderAddDlg
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(674, 293);
            this.Controls.Add(this.m_txt_policy_path);
            this.Controls.Add(this.m_btn_policy_choise);
            this.Controls.Add(this.m_cbx_stage);
            this.Controls.Add(this.m_btn_cancel);
            this.Controls.Add(this.m_btn_ok);
            this.Controls.Add(this.m_txb_materialNo);
            this.Controls.Add(this.m_txb_orderNo);
            this.Controls.Add(this.label4);
            this.Controls.Add(this.label7);
            this.Controls.Add(this.label3);
            this.Controls.Add(this.label1);
            this.Controls.Add(this.label2);
            this.Font = new System.Drawing.Font("新宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "WorkOrderAddDlg";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterParent;
            this.Text = "创建本地工单样本";
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion
        private System.Windows.Forms.Label label2;
        private System.Windows.Forms.TextBox m_txb_orderNo;
        private System.Windows.Forms.Label label3;
        private System.Windows.Forms.TextBox m_txb_materialNo;
        private System.Windows.Forms.Label label4;
        private System.Windows.Forms.Label label7;
        private System.Windows.Forms.Button m_btn_ok;
        private System.Windows.Forms.Button m_btn_cancel;
        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.ComboBox m_cbx_stage;
        private System.Windows.Forms.TextBox m_txt_policy_path;
        private System.Windows.Forms.Button m_btn_policy_choise;
    }
}