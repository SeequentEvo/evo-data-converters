using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

using Deswik.Core.Structures;
using Deswik.Duf;
using Deswik.Entities;
using Deswik.Entities.Base;
using Deswik.Entities.Cad;
using Deswik.Serialization;

using SharedCode;

namespace SimpleDuf
{

    public class SimpleEntity
    {
        public Guid Guid { get; private set; }
        protected DufDocument Duf;


        public SimpleEntity(DufDocument document, Guid guid)
        {
            Guid = guid;
            Duf = document;
        }


        private Primary GetPrimary(Guid guid)
        {
            var result = Duf.GetEntityByGuid(guid);
            var primary = result as Primary;
            if (result == null)
            {
                throw new Exception("Entity is not a Primary");
            }
            return primary;
        }

        public Primary Entity
        {
            get
            {
                return GetPrimary(Guid);
            }
        }
    }



    public class SimpleLayer : SimpleEntity
    {
        private DufAttributes _attributes;
        public SimpleLayer(DufDocument document, Guid guid) : base(document, guid)
        {

            var layer = Entity as Layer;
            if (layer == null)
            {
                // TODO better exception
                throw new Exception("Bad type");
            }

            // TODO The layer should gather its attributes on construction
            _attributes = new DufAttributes(layer);
        }

        private static Dictionary<string, DufAttributes.Attribute.AttributeType> TypeLookup = new Dictionary<string, DufAttributes.Attribute.AttributeType>()
            {
                { "String", DufAttributes.Attribute.AttributeType.String },
                { "DateTime", DufAttributes.Attribute.AttributeType.DateTime },
                { "Double", DufAttributes.Attribute.AttributeType.Double },
                { "Integer", DufAttributes.Attribute.AttributeType.Integer },
            };

        public DufAttributes.Attribute AddAttribute(string name, string type_str)
        {
            // TODO Guard agianst adding the same attribute twice
            // TODO Should just bind the enum if that's possible

            if (TypeLookup.ContainsKey(type_str))
            {
                var newAttribute = new DufAttributes.Attribute() { Name = name, Type = TypeLookup[type_str] };
                _attributes.Add(newAttribute);
                return newAttribute;
            }
            else
            {
                throw new ArgumentException("Type must be one of [String, DateTime, Double, Integer]");
            }
        }
    }

    public class SimpleFigure : SimpleEntity
    {
        // TODO I'm avoiding modifying DufDocuments for now. But there's no reason this class should have to keep track of its parent.
        protected Guid _parentLayer;

        public SimpleFigure(DufDocument document, Guid guid, Guid parentLayer) : base(document, guid)
        {
            _parentLayer = parentLayer;
        }

        public void SetAttribute(DufAttributes.Attribute attribute, object value)
        {
            // TODO Guard against bad types. Probably better done in the Attribute class.
            attribute.SetOnEntity(Entity, value);
        }
    }

    public class SimplePolyline : SimpleFigure
    {
        

        public SimplePolyline(DufDocument document, Guid guid, Guid parentLayer) : base(document, guid, parentLayer)
        {
        }

        static void GetBounds(DufList<Vector4_dp> vertices, out Vector3_dp minBounds, out Vector3_dp maxBounds)
        {
            double minX = double.MaxValue;
            double minY = double.MaxValue;
            double minZ = double.MaxValue;
            double maxX = double.MinValue;
            double maxY = double.MinValue;
            double maxZ = double.MinValue;

            foreach (var vertex in vertices)
            {
                var x = vertex.X;
                var y = vertex.Y;
                var z = vertex.Z;

                if (x < minX) { minX = x; }
                if (x > maxX) { maxX = x; }
                if (y < minY) { minY = y; }
                if (y > maxY) { maxY = y; }
                if (z < minZ) { minZ = z; }
                if (z > maxZ) { maxZ = z; }
            }

            minBounds = new Vector3_dp(minX, minY, minZ);
            maxBounds = new Vector3_dp(maxX, maxY, maxZ);
        }

        public void SetVertices3D(double[] vertices, bool ensureClosed = false)
        {
            var polyline = Entity as dwPolyline;
            if (polyline == null)
            {
                // TODO better exception
                throw new Exception("Bad type");
            }

            if (vertices.Length % 3 != 0)
            {
                // TODO throw better exception?
                throw new Exception("Vertices length not a multiple of 3");
            }

            var verticesCount = vertices.Length;
            int capacity = verticesCount / 3;

            bool needsClose = ensureClosed && (vertices[verticesCount - 3] != vertices[0] || vertices[verticesCount - 2] != vertices[1] || vertices[verticesCount - 1] != vertices[2]);
            if (needsClose)
            {
                capacity += 1;
            }

            var vertexList = new DufList<Vector4_dp>(capacity);
            int i = 0;

            while (i < verticesCount)
            {
                var x = vertices[i++];
                var y = vertices[i++];
                var z = vertices[i++];

                vertexList.Add(new Vector4_dp(x, y, z, 0));
            }

            if (needsClose)
            {
                vertexList.Add(new Vector4_dp(vertices[0], vertices[1], vertices[2], 0));
            }

            polyline.VertexList = vertexList;

            GetBounds(polyline.VertexList, out var minBounds, out var maxBounds);


            Duf.SetMetadataForEntity(polyline, minBounds, maxBounds, _parentLayer);
        }
    }


    public class Duf
    {
        private DufDocument _duf;

        public Duf(string path)
        {
            _duf = new DufDocument(path);
            _duf.LoadReferenceEntities();
            _duf.LoadModelEntities();
        }

        public SimpleEntity NewLayer(string name, Guid? parentLayer = null)
        {
            var newLayer = _duf.AddLayer(name, parentLayer);
            return new SimpleLayer(_duf, newLayer.Guid);
        }

        public void AddFigure(Figure figure, Guid layerGuid)
        {
            _duf.AddEntity(figure, parentGuid: layerGuid);
            var layer = _duf.GetEntityByGuid(layerGuid) as Layer;
            if (layer == null)
            {
                throw new Exception("Not a layer");
            }
            figure.Layer = layer;
        }

        public SimpleEntity NewPolyline(Guid parentLayer)
        {
            var newPolyline = new dwPolyline();
            AddFigure(newPolyline, parentLayer);
            return new SimplePolyline(_duf, newPolyline.Guid, parentLayer);
        }

        public SimpleEntity NewPolyline(SimpleLayer parentLayer)
        {
            return NewPolyline(parentLayer.Guid);
        }

        public void Save()
        {
            _duf.Save();
        }

        public void Dispose()
        {
            _duf.Dispose();
        }

    }
}
