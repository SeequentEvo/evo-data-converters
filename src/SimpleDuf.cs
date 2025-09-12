using System;
using System.Collections.Concurrent;
using System.Collections.Generic;
using System.Linq;
using System.Security.Principal;
using System.Threading.Tasks;

using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Cad;
using Deswik.Serialization;

namespace SimpleDuf
{
    public class DufDocument : IDisposable
    {
        private static readonly Guid _documentPaletteGuid = new Guid("8876D917-BF46-4F20-B6CB-8410B642F784");

        public string Path { get; protected set; }

        private DufImplementation<Category> _duf { get; set; }

        private GuidReferences _guidReferences;

        private Dictionary<Category, List<BaseEntity>> _entitiesByCategory;

        private DocumentPalette _documentPalette;

        private Document _document;

        public DufDocument(string path)
        {
            Path = path;

            _duf = new DufImplementation<Category>(Path, new Deswik.Entities.Cad.Activator(), new Deswik.Entities.Cad.Upgrader());

            _guidReferences = new GuidReferences();

            _entitiesByCategory = new Dictionary<Category, List<BaseEntity>>();

            _entitiesByCategory[Category.Palette] = new List<BaseEntity>();
            _entitiesByCategory[Category.LineTypes] = new List<BaseEntity>();
            _entitiesByCategory[Category.Layers] = new List<BaseEntity>();
            _entitiesByCategory[Category.Images] = new List<BaseEntity>();
            _entitiesByCategory[Category.TextStyles] = new List<BaseEntity>();
            _entitiesByCategory[Category.Blocks] = new List<BaseEntity>();
            _entitiesByCategory[Category.DimStyles] = new List<BaseEntity>();
            _entitiesByCategory[Category.HatchPatterns] = new List<BaseEntity>();
            _entitiesByCategory[Category.Lights] = new List<BaseEntity>();
            _entitiesByCategory[Category.ModelEntities] = new List<BaseEntity>();
            _entitiesByCategory[Category.Document] = new List<BaseEntity>();
        }

        // TODO - Probably best not to give the client the option of having an unloaded document
        public void Load()
        {
            LoadReferenceEntities();
            LoadModelEntities();
        }

        public void Dispose()
        {
            _duf?.Dispose();
        }

        public Layer GetLayerByName(string layer_str)
        {
            List<ItemHeader> layer_headers = _duf.GetEntityHeadersWithName(Category.Layers, layer_str);
            ItemHeader layer_header = layer_headers[0];
            Guid layer_guid = layer_header.EntityGuid;

            BaseEntity base_entity = GetEntityByGuid(layer_guid);
            Layer layer = base_entity as Layer;

            return layer;
        }

        public BaseEntity GetEntityByGuid(Guid guid)
        {
            return _guidReferences?.GetEntity(guid);
        }

        private void LoadModelEntities(Guid? layerGuid = null)
        {
            var loadedItems = new ConcurrentQueue<BaseEntity>();
            List<Guid?> parents = null;

            if (layerGuid != null)
            {
                parents = new List<Guid?> { layerGuid };
            }

            var loadTask = Task.Run(() => {
                _duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { ParentIds = parents, Categories = new List<Category> { Category.ModelEntities } }, false, true, null);
            });

            while (TaskNotFinished(loadTask) || !loadedItems.IsEmpty)
            {
                if (!loadedItems.TryDequeue(out var entity))
                {
                    System.Threading.Thread.Sleep(10);
                    continue;
                }

                AddLoadedEntity(Category.ModelEntities, entity);
            }
        }

        private void LoadReferenceEntities()
        {
            LoadTopLevelEntitiesOfType(Category.Palette);
            LoadTopLevelEntitiesOfType(Category.LineTypes);
            LoadTopLevelEntitiesOfType(Category.Layers);
            LoadTopLevelEntitiesOfType(Category.Images);
            LoadTopLevelEntitiesOfType(Category.TextStyles);
            LoadTopLevelEntitiesOfType(Category.Blocks);
            LoadTopLevelEntitiesOfType(Category.DimStyles);
            LoadTopLevelEntitiesOfType(Category.HatchPatterns);
            LoadTopLevelEntitiesOfType(Category.Lights);
            LoadTopLevelEntitiesOfType(Category.Document);

            if (_entitiesByCategory.TryGetValue(Category.Palette, out var paletteEntities))
            {
                _documentPalette = paletteEntities.OfType<DocumentPalette>().First();
            }

            if (_entitiesByCategory.TryGetValue(Category.Document, out var documentEntities))
            {
                _document = documentEntities.OfType<Document>().First();
            }
        }

        public void Save(string saveAsPath = null)
        {
            var existingDocGuid = _duf?.Header != null ? _duf.LoadFromLatest(null, new FilterCriteria<Category> { Categories = new List<Category> { Category.Document } }, true, false, null).FirstOrDefault()?.Guid : null;
            _duf.Save(GetSaveSets(existingDocGuid), GetUserName(), saveAsPath, true);
        }

        private void AddLoadedEntity(Category category, BaseEntity entity)
        {
            if (!_entitiesByCategory.TryGetValue(category, out var baseEntities))
            {
                baseEntities = new List<BaseEntity>();
                _entitiesByCategory.Add(category, baseEntities);
            }

            baseEntities.Add(entity);
        }

        /// <summary>
        ///     Returns true if the provided task is still executing
        /// </summary>
        /// <param name="task"></param>
        /// <returns></returns>
        private static bool TaskNotFinished(Task task)
        {
            return task.Status != TaskStatus.Canceled &&
                   task.Status != TaskStatus.Faulted &&
                   task.Status != TaskStatus.RanToCompletion;
        }

        private void LoadTopLevelEntitiesOfType(Category category)
        {
            var loadedItems = new ConcurrentQueue<BaseEntity>();
            var loadTask = Task.Run(() => {
                _duf.LoadFromLatestWithConcurrentQueue(loadedItems, _guidReferences, new FilterCriteria<Category> { Categories = new List<Category> { category } }, false, true, null);
            });

            while (TaskNotFinished(loadTask) || !loadedItems.IsEmpty)
            {
                BaseEntity entity;
                if (!loadedItems.TryDequeue(out entity))
                {
                    System.Threading.Thread.Sleep(10);
                    continue;
                }

                AddLoadedEntity(category, entity);
            }
        }

        private void SetDocumentPalette()
        {
            if (_documentPalette == null)
            {
                _documentPalette = new DocumentPalette
                {
                    Guid = _documentPaletteGuid
                };

                _documentPalette.Palette = new Palette(); // TODO: populate this with sensible values
            }
        }

        private IEnumerable<SaveSet<Category>> GetSaveSets(Guid? existingDocGuid, bool maintainEntityOrdering = false)
        {
            var _guidReferences = new GuidReferences();

            SetDocumentPalette();

            yield return new SaveByEnumerableSet<Category>(new[] { new SaveEntityItem(_documentPalette) }, Category.Palette, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.LineTypes].Select(x => new SaveEntityItem(x)), Category.LineTypes, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Images].Select(x => new SaveEntityItem(x)), Category.Images, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Layers].Select(x => new SaveEntityItem(x)), Category.Layers, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.TextStyles].Select(x => new SaveEntityItem(x)), Category.TextStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var dufBlocks = new List<BaseEntity>();
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Blocks].Select(x =>
            {
                dufBlocks.Add(x);
                return new SaveEntityItem(x);
            }), Category.Blocks, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, false);

            // NOTE: we add block refs at end not during serialization
            foreach (var block in dufBlocks)
            {
                _guidReferences.AddEntity(block);
            }

            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.DimStyles].Select(x => new SaveEntityItem(x)), Category.DimStyles, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.HatchPatterns].Select(x => new SaveEntityItem(x)), Category.HatchPatterns, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
            yield return new SaveByEnumerableSet<Category>(_entitiesByCategory[Category.Lights].Select(x => new SaveEntityItem(x)), Category.Lights, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);

            var modelEntities = _entitiesByCategory[Category.ModelEntities].OfType<Figure>().ToArray();

            yield return new SaveByIndexSet<Category>((entityData) =>
            {
                if (entityData.Position >= modelEntities.Length)
                {
                    entityData.Finished = true;
                    return;
                }

                var entity = modelEntities[entityData.Position];

                if (maintainEntityOrdering && entity is Figure figure)
                {
                    figure.FigureOrder = (uint)entityData.Position + 1;
                }

                entityData.Entity = entity;
            },
            (entityMetadata) =>
            {
                var figure = modelEntities[entityMetadata.Position];
                var layerGuid = figure.Layer.Guid;
                var header = _duf.GetEntityHeader(figure.Guid);

                if (header is ItemHeader ih)
                {
                    if (ih.MinX is double minX && ih.MinY is double minY && ih.MinZ is double minZ && ih.MaxX is double maxX && ih.MaxY is double maxY && ih.MaxZ is double maxZ)
                    {
                        entityMetadata.EntityMetadata = new EntityMetadata(new Vector3_dp(minX, minY, minZ), new Vector3_dp(maxX, maxY, maxZ), layerGuid);
                    }
                }
                else
                {
                    entityMetadata.EntityMetadata = new EntityMetadata(layerGuid);
                }
            }, Category.ModelEntities, false, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, false);

            if (_document.Guid.Equals(Guid.Empty))
            {
                _document.Guid = existingDocGuid ?? Guid.NewGuid();
            }

            yield return new SaveByEnumerableSet<Category>(new[] { new SaveEntityItem(_document) }, Category.Document, true, _guidReferences, new PerformanceTweaking { NumberCpuThreads = 1 }, true);
        }

        private static string GetUserName()
        {
            string username = null;

            try
            {
                username = WindowsIdentity.GetCurrent().Name;
            }
            catch
            {
                try
                {
                    username = Environment.UserName;
                }
                catch
                {
                    // ignored
                }
            }

            if (string.IsNullOrWhiteSpace(username)) username = "unknown";

            return username;
        }
    }
}
