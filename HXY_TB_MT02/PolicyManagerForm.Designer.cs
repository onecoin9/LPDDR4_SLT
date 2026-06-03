namespace Hsg.View
{
    partial class PolicyManagerForm
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
            System.ComponentModel.ComponentResourceManager resources = new System.ComponentModel.ComponentResourceManager(typeof(PolicyManagerForm));
            this.label1 = new System.Windows.Forms.Label();
            this.btn_add_new = new System.Windows.Forms.Button();
            this.btn_edit_item = new System.Windows.Forms.Button();
            this.btn_delete = new System.Windows.Forms.Button();
            this.btn_view = new System.Windows.Forms.Button();
            this.m_txt_policy_path = new System.Windows.Forms.TextBox();
            this.m_btn_policy_choise = new System.Windows.Forms.Button();
            this.SuspendLayout();
            // 
            // label1
            // 
            this.label1.AutoSize = true;
            this.label1.Location = new System.Drawing.Point(3, 35);
            this.label1.Margin = new System.Windows.Forms.Padding(4, 0, 4, 0);
            this.label1.Name = "label1";
            this.label1.Size = new System.Drawing.Size(123, 24);
            this.label1.TabIndex = 0;
            this.label1.Text = "现有方案:";
            // 
            // btn_add_new
            // 
            this.btn_add_new.Location = new System.Drawing.Point(150, 136);
            this.btn_add_new.Name = "btn_add_new";
            this.btn_add_new.Size = new System.Drawing.Size(112, 49);
            this.btn_add_new.TabIndex = 2;
            this.btn_add_new.Text = "新增";
            this.btn_add_new.UseVisualStyleBackColor = true;
            this.btn_add_new.Click += new System.EventHandler(this.OnBtnAddClick);
            // 
            // btn_edit_item
            // 
            this.btn_edit_item.Location = new System.Drawing.Point(402, 136);
            this.btn_edit_item.Name = "btn_edit_item";
            this.btn_edit_item.Size = new System.Drawing.Size(112, 49);
            this.btn_edit_item.TabIndex = 2;
            this.btn_edit_item.Text = "修改";
            this.btn_edit_item.UseVisualStyleBackColor = true;
            this.btn_edit_item.Click += new System.EventHandler(this.OnBtnEditClick);
            // 
            // btn_delete
            // 
            this.btn_delete.Location = new System.Drawing.Point(528, 136);
            this.btn_delete.Name = "btn_delete";
            this.btn_delete.Size = new System.Drawing.Size(112, 49);
            this.btn_delete.TabIndex = 2;
            this.btn_delete.Text = "删除";
            this.btn_delete.UseVisualStyleBackColor = true;
            this.btn_delete.Click += new System.EventHandler(this.OnBtnDeleteClick);
            // 
            // btn_view
            // 
            this.btn_view.Location = new System.Drawing.Point(276, 136);
            this.btn_view.Name = "btn_view";
            this.btn_view.Size = new System.Drawing.Size(112, 49);
            this.btn_view.TabIndex = 2;
            this.btn_view.Text = "查看";
            this.btn_view.UseVisualStyleBackColor = true;
            this.btn_view.Click += new System.EventHandler(this.OnBtnViewClick);
            // 
            // m_txt_policy_path
            // 
            this.m_txt_policy_path.Location = new System.Drawing.Point(94, 32);
            this.m_txt_policy_path.Name = "m_txt_policy_path";
            this.m_txt_policy_path.ReadOnly = true;
            this.m_txt_policy_path.Size = new System.Drawing.Size(652, 35);
            this.m_txt_policy_path.TabIndex = 15;
            this.m_txt_policy_path.TextChanged += new System.EventHandler(this.m_txt_policy_path_TextChanged);
            // 
            // m_btn_policy_choise
            // 
            this.m_btn_policy_choise.Location = new System.Drawing.Point(752, 26);
            this.m_btn_policy_choise.Name = "m_btn_policy_choise";
            this.m_btn_policy_choise.Size = new System.Drawing.Size(108, 35);
            this.m_btn_policy_choise.TabIndex = 14;
            this.m_btn_policy_choise.Text = "选择";
            this.m_btn_policy_choise.UseVisualStyleBackColor = true;
            this.m_btn_policy_choise.Click += new System.EventHandler(this.OnSelectBtnClick);
            // 
            // PolicyManagerForm
            // 
            this.AutoScaleDimensions = new System.Drawing.SizeF(13F, 24F);
            this.AutoScaleMode = System.Windows.Forms.AutoScaleMode.Font;
            this.ClientSize = new System.Drawing.Size(870, 234);
            this.Controls.Add(this.m_txt_policy_path);
            this.Controls.Add(this.m_btn_policy_choise);
            this.Controls.Add(this.btn_edit_item);
            this.Controls.Add(this.btn_delete);
            this.Controls.Add(this.btn_view);
            this.Controls.Add(this.btn_add_new);
            this.Controls.Add(this.label1);
            this.Font = new System.Drawing.Font("宋体", 12F, System.Drawing.FontStyle.Bold, System.Drawing.GraphicsUnit.Point, ((byte)(134)));
            this.Icon = ((System.Drawing.Icon)(resources.GetObject("$this.Icon")));
            this.Margin = new System.Windows.Forms.Padding(4);
            this.Name = "PolicyManagerForm";
            this.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen;
            this.Text = "测试方案管理";
            this.ResumeLayout(false);
            this.PerformLayout();

        }

        #endregion

        private System.Windows.Forms.Label label1;
        private System.Windows.Forms.Button btn_add_new;
        private System.Windows.Forms.Button btn_edit_item;
        private System.Windows.Forms.Button btn_delete;
        private System.Windows.Forms.Button btn_view;
        private System.Windows.Forms.TextBox m_txt_policy_path;
        private System.Windows.Forms.Button m_btn_policy_choise;
    }
}