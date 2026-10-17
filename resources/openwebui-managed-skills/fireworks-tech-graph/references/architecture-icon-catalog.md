# 通用技術架構圖示目錄 v1

64 個原創向量圖示由伺服器直接載入，模型只選 ID，不寫 SVG 原始碼。未指定 ID 時依 label/detail 自動選擇。圖示不表示品牌官方產品外觀。

| 分類 | 可用 icon ID |
| --- | --- |
| 網路 | router（路由器）、switch（交換器）、rdma-switch、aggregation-switch（匯聚）、access-point、mesh、ethernet、fiber |
| 運算 | workstation、mini-pc、laptop、server、gpu、cpu、npu、network-card |
| 儲存 | nas、storage-array、disk、ssd、database、object-storage、memory、backup |
| 安全 | firewall、vpn、shield、lock、key、identity、zero-trust、gateway |
| 終端 | desktop、smartphone、tablet、users、camera、iot、edge-node、building |
| AI | ai-model、inference、training、agent、model-weights、embeddings、vector-db、pipeline |
| 軟體 | api、mcp、container、cluster、app、code、browser、cloud |
| 維運 | dashboard、monitoring、logs、analytics、load-balancer、queue、power、cooling |

大型匯聚／核心交換器獨立一層，同一層放平行設備。保留實際分支與連線，勿為排版捏造新設備。交換器已知埠數才填 port_groups；泛稱「25G 交換器」不代表已知埠數。

圖庫預覽：`/static/architecture-icons/v1/preview.html`。可搜尋與複製 SVG，另有整包 ZIP。可用這些字測試：NAS、VPN、GPU、交換器、AI 工作站、PCIe 網卡。
